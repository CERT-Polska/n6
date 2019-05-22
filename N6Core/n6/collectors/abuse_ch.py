# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
Collectors: abuse-ch.spyeye-doms, abuse-ch.spyeye-ips,
abuse-ch.zeus-doms, abuse-ch.zeus-ips, abuse-ch.zeustracker,
abuse-ch.palevo-doms, abuse-ch.palevo-ips, abuse-ch.feodotracker,
abuse-ch.ransomware, abuse-ch.ssl-blacklist,
abuse-ch.ssl-blacklist-dyre, abuse-ch.urlhaus-urls
"""

import csv
import json
import re
import sys
from collections import MutableMapping
from cStringIO import StringIO
from datetime import datetime

from lxml import html
from lxml.etree import ParserError, XMLSyntaxError

from n6.collectors.generic import (
    BaseRSSCollector,
    BaseUrlDownloaderCollector,
    BaseOneShotCollector,
    CollectorWithStateMixin,
    entry_point_factory,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class NoNewDataException(Exception):

    """
    Exception raised when the source does not provide any new data.
    """


class _BaseAbuseChMixin(object):

    raw_format_version_tag = '201406'
    type = 'blacklist'

    def process_data(self, data):
        return data


class AbuseChSpyeyeDomsCollector(_BaseAbuseChMixin, BaseUrlDownloaderCollector, BaseOneShotCollector):

    config_group = "abusech_spyeye_doms"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "spyeye-doms"


class AbuseChSpyeyeIpsCollector(_BaseAbuseChMixin, BaseUrlDownloaderCollector, BaseOneShotCollector):

    config_group = "abusech_spyeye_ips"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "spyeye-ips"


class AbuseChZeusDomsCollector(_BaseAbuseChMixin, BaseUrlDownloaderCollector, BaseOneShotCollector):

    config_group = "abusech_zeus_doms"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "zeus-doms"


class AbuseChZeusIpsCollector(_BaseAbuseChMixin, BaseUrlDownloaderCollector, BaseOneShotCollector):

    config_group = "abusech_zeus_ips"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "zeus-ips"


class AbuseChPalevoDomsCollector(_BaseAbuseChMixin, BaseUrlDownloaderCollector, BaseOneShotCollector):

    config_group = "abusech_palevo_doms"
    content_type = 'text/plain'

    def get_source_channel(self, **kwargs):
        return "palevo-doms"


class AbuseChPalevoIpsCollector(_BaseAbuseChMixin, BaseUrlDownloaderCollector, BaseOneShotCollector):

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


class AbuseChFeodoTrackerCollector(BaseRSSCollector):

    config_group = "abusech_feodotracker"

    def get_source_channel(self, **kwargs):
        return 'feodotracker'

    def rss_item_to_relevant_data(self, item):
        description = None
        for i in item:
            if i.tag == 'description':
                description = i.text
        return (description)


class AbuseChRansomwareTrackerCollector(CollectorWithStateMixin,
                                        BaseUrlDownloaderCollector,
                                        BaseOneShotCollector):

    type = 'file'
    config_group = "abusech_ransomware"
    content_type = 'text/csv'
    timestamp_pattern = '%Y-%m-%d %H:%M:%S'

    def __init__(self, *args, **kwargs):
        super(AbuseChRansomwareTrackerCollector, self).__init__(*args, **kwargs)
        self._state = self.load_state()
        if not isinstance(self._state, MutableMapping):
            self._state = {
                'timestamp': None,
            }
        if not self._state['timestamp']:  # first run of collector
            self.timestamp = '1970-01-01 00:00:00'
        else:
            self.timestamp = self._state['timestamp']

    def get_source_channel(self, **kwargs):
        return "ransomware"

    def process_data(self, data):
        output = StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"')
        rows = csv.reader(StringIO(data), delimiter=',', quotechar='"')
        newest_entry = None
        for row in rows:
            if not row or row[0].startswith('#'):
                continue
            timestamp = datetime.strptime(row[0], self.timestamp_pattern)
            if not newest_entry:
                newest_entry = row[0]
            if timestamp > datetime.strptime(self.timestamp, self.timestamp_pattern):
                writer.writerow(row)
            else:
                break
        if newest_entry:
            self._state['timestamp'] = newest_entry
        return output.getvalue()

    def start_publishing(self):
        """
        Extend the method to save the date of the latest entry.
        """
        super(AbuseChRansomwareTrackerCollector, self).start_publishing()
        self.save_state(self._state)


class _AbuseChSSLBlacklistBaseCollector(CollectorWithStateMixin, BaseRSSCollector):

    """
    Base collector class for 'SSL Blacklist' and 'SSL Blacklist Dyre'
    sources.

    Note that, contrary to their names, they are *event-based* sources.
    """

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
        super(_AbuseChSSLBlacklistBaseCollector, self).__init__(*args, **kwargs)
        self._rss_feed_url = self.config['url']
        # separate timeouts for downloading detail pages
        self._details_download_timeout = int(self.config.get('details_download_timeout', 12))
        self._details_retry_timeout = int(self.config.get('details_retry_timeout', 4))
        # attribute to store data created from
        # detail pages, before deduplication
        self._complete_data = None

    def run_handling(self):
        try:
            self._output_components = self.get_output_components(**self.input_data)
        except NoNewDataException:
            LOGGER.info('No new data from the %s source.', self.source_name)
        else:
            self.run()
        self.save_state(self._complete_data)
        LOGGER.info('Stopped')

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


class AbuseChSSLBlacklistCollector(CollectorWithStateMixin,
                                   BaseUrlDownloaderCollector,
                                   BaseOneShotCollector):

    config_spec = '''
        [abusech_ssl_blacklist]
        source :: str
        cache_dir :: str
        url :: str
        download_timeout :: int
        retry_timeout :: int
    '''
    raw_format_version_tag = '201902'
    type = 'file'
    content_type = 'text/csv'


    def run_handling(self):
        self._state = self._load_state_or_get_default_state()
        # see BaseUrlDownloaderCollector.run_handling()
        super(AbuseChSSLBlacklistCollector, self).run_handling()


    def _load_state_or_get_default_state(self):
        state = self.load_state()
        if state is None:
            state = {'time': '', 'sha1s': set()}
        return state


    def process_data(self, data):
        all_rows = data.split('\n')
        fresh_rows = self._get_fresh_rows_only(all_rows)
        if fresh_rows:
            return '\n'.join(fresh_rows)
        return None


    def _get_fresh_rows_only(self, all_rows):
        # the *previously newest* abuse time
        prev_newest_time = self._state['time']

        # abuse IDs from the rows with the *previously newest* abuse time
        # that have already been collected
        prev_newest_time_sha1s = self._state['sha1s']

        newest_time = None
        newest_time_sha1s = set()
        fresh_rows = []

        preceding_row_time = None  # (for asserts only)

        for row in all_rows:
            if row.startswith('#') or not row.strip():
                # row is commented or blank -> skip it
                continue

            # each row (if not commented or blank) consists of (possibly
            # quoted, comma-separated):
            # 1) listing date (abuse time in some *sortable* format (ISO-8601-like)),
            # 2) abuse SHA1,
            # 3) listing reason (irrelevant here)
            (row_time,
             row_sha1,
             _) = [column for column in row.split(',', 2)]

            if __debug__:
                # we assume that time values in consecutive rows are monotonic
                # (non-increasing, possibly repeating)
                assert (preceding_row_time is None
                        or row_time <= preceding_row_time)
                preceding_row_time = row_time

            if row_time < prev_newest_time:
                # stop collecting when reached rows which are old enough
                # that we are sure they must have already been collected
                break

            if newest_time is None:
                # this is the first (newest) actual (not blank/commented)
                # row in the downloaded file -- so here we have the *newest*
                # abuse time
                newest_time = row_time

            if row_time == newest_time:
                # this row is amongst those with the *newest* abuse time
                newest_time_sha1s.add(row_sha1)

            if row_sha1 in prev_newest_time_sha1s:
                # this row is amongst those with the *previously newest*
                # abuse time, *and* we know that it has already been
                # collected -> so we *skip* it
                assert row_time == prev_newest_time
                continue

            # this row have *not* been collected yet -> let's collect it
            # now (in its original form, i.e., without any modifications)
            fresh_rows.append(row)

        if fresh_rows:
            self._state = {
                # the *newest* abuse time
                'time': newest_time,
                # abuse SHA1s from all rows with the *newest* abuse time
                'sha1s': newest_time_sha1s,
            }
        return fresh_rows


    def get_output_prop_kwargs(self, source, output_data_body, **processed_data):
        if output_data_body is None:
            # process_data() [see above...] returned None (nothing to be published)
            return None
        # see BaseUrlDownloaderCollector.get_output_prop_kwargs()
        return super(AbuseChSSLBlacklistCollector, self).get_output_prop_kwargs(source,
                                                                                output_data_body,
                                                                                **processed_data)


    # note: this method is called *only*
    # [see BaseUrlDownloaderCollector.run_handling()]
    # if process_data() [see above...] returned some data (not None)
    def start_publishing(self):
        # see BaseOneShotCollector.start_publishing()
        super(AbuseChSSLBlacklistCollector, self).start_publishing()
        self.save_state(self._state)


    @property
    def source_name(self):
        return "Abuse.ch SSL Blacklist Collector"

    def get_source_channel(self, **kwargs):
        return "ssl-blacklist"


class AbuseChSSLBlacklistDyreCollector(_AbuseChSSLBlacklistBaseCollector):

    config_group = "abuse_ch_ssl_blacklist_dyre"

    @property
    def source_name(self):
        return "Abuse.ch SSL Blacklist Collector - Dyre"

    def get_source_channel(self, **kwargs):
        return "ssl-blacklist-dyre"



class AbuseChUrlhausUrls(CollectorWithStateMixin,
                         BaseUrlDownloaderCollector,
                         BaseOneShotCollector):

    config_spec = '''
        [abusech_urlhaus_urls]
        source :: str
        cache_dir :: str
        url :: str
        download_timeout :: int
        retry_timeout :: int
    '''

    type = 'file'
    content_type = 'text/csv'


    def __init__(self, *args, **kwargs):
        super(AbuseChUrlhausUrls, self).__init__(*args, **kwargs)
        self.url = self.config['url']
        self._state = None  # to be set in run_handling()


    def run_handling(self):
        self._state = self._load_state_or_get_default_state()
        super(AbuseChUrlhausUrls,
              self).run_handling()  # see BaseUrlDownloaderCollector.run_handling()


    def _load_state_or_get_default_state(self):
        state = self.load_state()
        if state is None:
            state = {'time': '', 'ids': set()}
        return state


    def get_source_channel(self, **kwargs):
        return 'urlhaus-urls'


    # see BaseUrlDownloaderCollector.get_output_data_body()
    def process_data(self, data):
        all_rows = data.split('\n')
        fresh_rows = self._get_fresh_rows_only(all_rows)
        if fresh_rows:
            return '\n'.join(fresh_rows)
        return None


    def _get_fresh_rows_only(self, all_rows):
        # the *previously newest* abuse time
        prev_newest_time = self._state['time']

        # abuse IDs from the rows with the *previously newest* abuse time
        # that have already been collected
        prev_newest_time_ids = self._state['ids']

        newest_time = None
        newest_time_ids = set()
        fresh_rows = []

        preceding_row_time = None  # (for asserts only)

        for row in all_rows:
            if row.startswith('#') or not row.strip():
                # row is commented or blank -> skip it
                continue

            # each row (if not commented or blank) consists of (possibly
            # quoted, comma-separated):
            # 1) *unique* abuse ID (its format is irrelevant),
            # 2) abuse time in some *sortable* format (ISO-8601-like),
            # 3) other fields (irrelevant here)
            (abuse_id,
             row_time,
             _) = [column.strip().strip('"') for column in row.split(',', 2)]

            if __debug__:
                # we assume that time values in consecutive rows are monotonic
                # (non-increasing, possibly repeating)
                assert (preceding_row_time is None
                        or row_time <= preceding_row_time)
                preceding_row_time = row_time

            if row_time < prev_newest_time:
                # stop collecting when reached rows which are old enough
                # that we are sure they must have already been collected
                break

            if newest_time is None:
                # this is the first (newest) actual (not blank/commented)
                # row in the downloaded file -- so here we have the *newest*
                # abuse time
                newest_time = row_time

            if row_time == newest_time:
                # this row is amongst those with the *newest* abuse time
                newest_time_ids.add(abuse_id)

            if abuse_id in prev_newest_time_ids:
                # this row is amongst those with the *previously newest*
                # abuse time, *and* we know that it has already been
                # collected -> so we *skip* it
                assert row_time == prev_newest_time
                continue

            # this row have *not* been collected yet -> let's collect it
            # now (in its original form, i.e., without any modifications)
            fresh_rows.append(row)

        if fresh_rows:
            fresh_newest_time_ids = newest_time_ids - prev_newest_time_ids
            assert newest_time and fresh_newest_time_ids
        else:
            assert (newest_time is None and not newest_time_ids
                    or
                    newest_time == prev_newest_time and newest_time_ids == prev_newest_time_ids)

        self._state = {
            'time': newest_time,     # the *newest* abuse time
            'ids': newest_time_ids,  # abuse IDs from all rows with the *newest* abuse time
        }
        return fresh_rows


    def get_output_prop_kwargs(self, source, output_data_body, **processed_data):
        if output_data_body is None:
            # process_data() [see above...] returned None (nothing to be published)
            return None
        # see BaseUrlDownloaderCollector.get_output_prop_kwargs()
        return super(AbuseChUrlhausUrls, self).get_output_prop_kwargs(source,
                                                                      output_data_body,
                                                                      **processed_data)


    # note: this method is called *only* [see BaseUrlDownloaderCollector.run_handling()]
    # if process_data() [see above...] returned some data (not None)
    def start_publishing(self):
        # see BaseOneShotCollector.start_publishing()
        super(AbuseChUrlhausUrls, self).start_publishing()
        self.save_state(self._state)


entry_point_factory(sys.modules[__name__])

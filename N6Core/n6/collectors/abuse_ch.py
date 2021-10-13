# Copyright (c) 2013-2021 NASK. All rights reserved.

"""
Collectors: abuse-ch.spyeye-doms, abuse-ch.spyeye-ips,
abuse-ch.zeus-doms, abuse-ch.zeus-ips, abuse-ch.zeustracker,
abuse-ch.palevo-doms, abuse-ch.palevo-ips, abuse-ch.feodotracker,
abuse-ch.ransomware, abuse-ch.ssl-blacklist,
abuse-ch.ssl-blacklist-dyre, abuse-ch.urlhaus-urls,
abuse-ch.urlhaus-payloads-urls, abuse-ch.urlhaus-payloads
"""

import contextlib
import json
import operator
import os
import re
import shutil
import sys
import tempfile

import more_itertools
from bs4 import BeautifulSoup
from czipfile import ZipFile
from lxml import html
from lxml.etree import (
    ParserError,
    XMLSyntaxError,
)

from n6.collectors.generic import (
    BaseCollector,
    BaseDownloadingTimeOrderedRowsCollector,
    BaseOneShotCollector,
    BaseRSSCollector,
    BaseUrlDownloaderCollector,
    CollectorWithStateMixin,
    entry_point_factory,
)
from n6lib.common_helpers import (
    make_exc_ascii_str,
    read_file,
)
from n6lib.config import join_config_specs
from n6lib.csv_helpers import (
    extract_field_from_csv_row,
    split_csv_row,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import get_logger
from n6lib.unpacking_helpers import iter_unzip_from_bytes



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
            # got `state` in a legacy form
            row_time = self.normalize_row_time(state[self.row_time_legacy_state_key])
            state = {
                # note: one or a few rows (those containing this "boundary"
                # time value) will be duplicated, but we can live with that
                self._NEWEST_ROW_TIME_STATE_KEY: row_time,
                self._NEWEST_ROWS_STATE_KEY: set(),
            }
        return state

    def pick_raw_row_time(self, row):
        return extract_field_from_csv_row(row, column_index=self.time_field_index).strip()

    def clean_row_time(self, raw_row_time):
        return self.normalize_row_time(raw_row_time)

    def normalize_row_time(self, raw_row_time):
        return str(parse_iso_datetime_to_utc(raw_row_time))


class AbuseChRansomwareTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    row_time_legacy_state_key = 'timestamp'
    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'ransomware'


class AbuseChFeodoTrackerCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    raw_format_version_tag = '202110'

    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'feodotracker'

    def split_orig_data_into_rows(self, orig_data):
        return reversed(orig_data.split('\n'))

    def should_row_be_used(self, row):
        if not row.strip() or row.startswith('#'):
            return False
        try:
            self.normalize_row_time(extract_field_from_csv_row(row, column_index=self.time_field_index))
            return True
        except ValueError:
            return False


class AbuseChSSLBlacklistCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):
    # Note that, contrary to its name, it is an *event-based* source

    raw_format_version_tag = '201902'

    row_time_legacy_state_key = 'time'
    time_field_index = 0

    def get_source_channel(self, **processed_data):
        return 'ssl-blacklist'


class AbuseChUrlhausUrlsCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    raw_format_version_tag = '202001'
    type = 'stream'

    config_spec_pattern = join_config_specs(
        BaseDownloadingTimeOrderedRowsCollector.config_spec_pattern,
        '''
            api_url :: str
            api_retries = 3 :: int
        ''')

    time_field_index = 1

    CSV_FILENAME = 'csv.txt'

    def get_source_channel(self, **processed_data):
        return 'urlhaus-urls'

    # note that since Apr 2020 AbuseCh changed input format for this
    # source - now it is .zip file with .txt inside
    def obtain_orig_data(self):
        data = self.download(self.config['url'])
        [(_, all_rows)] = iter_unzip_from_bytes(data, filenames=[self.CSV_FILENAME])
        return all_rows

    def prepare_selected_data(self, fresh_rows):
        abuse_info_dicts = [self._make_abuse_info_dict(row) for row in fresh_rows]
        return json.dumps(abuse_info_dicts)

    def _make_abuse_info_dict(self, row):
        abuse_info_dict = self._convert_row_to_info_dict(row)
        url_id = abuse_info_dict['url_id']
        url_info = self._fetch_url_info_from_api(url_id)
        abuse_info_dict['url_info_from_api'] = json.loads(url_info)
        return abuse_info_dict

    def _convert_row_to_info_dict(self, row):
        row_fields = split_csv_row(row)
        return {
            'url_id': row_fields[0],
            'dateadded': row_fields[1],
            'url': row_fields[2],
            'url_status': row_fields[3],
            'threat': row_fields[4],
            'tags': row_fields[5],
            'urlhaus_link': row_fields[6],
            'reporter': row_fields[7],
        }

    def _fetch_url_info_from_api(self, url_id):
        return RequestPerformer.fetch(method='POST',
                                      url=self.config['api_url'],
                                      data={'urlid': url_id},
                                      retries=self.config['api_retries'])


class AbuseChUrlhausPayloadsUrlsCollector(_BaseAbuseChDownloadingTimeOrderedRowsCollector):

    time_field_index = 0

    CSV_FILENAME = 'payload.txt'

    def get_source_channel(self, **processed_data):
        return 'urlhaus-payloads-urls'

    # note that since Apr 2020 AbuseCh changed input format for this
    # source - now it is .zip file with .txt inside
    def obtain_orig_data(self):
        data = self.download(self.config['url'])
        [(_, all_rows)] = iter_unzip_from_bytes(data, filenames=[self.CSV_FILENAME])
        return all_rows

    def prepare_selected_data(self, fresh_rows):
        return fresh_rows

    def clean_row_time(self, raw_row_time):
        try:
            return self.normalize_row_time(raw_row_time)
        except ValueError:
            return None

    def publish_iteratively(self):
        for chunk in more_itertools.chunked(self._selected_data, 20000):
            rk, body, prop_kwargs = self.get_output_components(selected_data="\n".join(chunk))
            self.publish_output(rk, body, prop_kwargs)
            yield
        yield self.FLUSH_OUT
        self.save_state(self._state)


class AbuseChUrlhausPayloadsCollector(CollectorWithStateMixin,
                                      BaseCollector):

    config_spec = '''
        [abusech_urlhaus_payloads]
        source :: str
        cache_dir :: str
        api_url :: str
        zip_files_url :: str
        zip_file_password :: str
        ignored_zip_filenames = :: list_of_zip_filenames
        oldest_zip_filename_to_collect = 2019-03-01.zip :: zip_filename
        newest_zip_filename_to_collect = "" :: zip_filename
    '''

    @property
    def custom_converters(self):
        return {
            'zip_filename': self._conv_zip_filename_from_config,
            'list_of_zip_filenames': self.make_list_converter(self._conv_zip_filename_from_config),
        }

    @classmethod
    def _conv_zip_filename_from_config(cls, zip_filename):
        if cls.VALID_ZIP_FILENAME_REGEX.search(zip_filename):
            return zip_filename
        if zip_filename == '':
            return None
        raise ValueError('not a "YYYY-MM-DD.zip"-like archive filename')

    type = 'file'
    content_type = 'application/octet-stream'

    output_queue = {
        'exchange': 'sample',
        'exchange_type': 'topic'
    }

    # The state stored on disk is a dict:
    # `{<ZIP filename>: <either string 'COMPLETED' or set of already processed MD5s from this ZIP>,
    #   ...}`.
    ZIP_COMPLETED_STATUS_TAG = 'COMPLETED'

    ARCHIVE_FILE_EXTENSION = '.zip'
    HTTP_RETRIES = 5
    TEMP_DIR_NAME_PREFIX = 'n6collector_abusechurlhauspayloads_'
    VALID_ZIP_FILENAME_REGEX = re.compile(r'\A\d{4}-\d{2}-\d{2}%s\Z'
                                          % re.escape(ARCHIVE_FILE_EXTENSION))
    VALID_PAYLOAD_FILENAME_REGEX = re.compile(r'\A[0-9a-f]{32}\Z')
    SAMPLE_EXCHANGE_META_HEADER_KEYS = [
        'md5_hash',
        'sha256_hash',
        'signature',
        'firstseen',
        'lastseen',
    ]


    class _PayloadInfoValidationError(Exception):
        """Raised when payload info data are not valid."""


    def __init__(self, *args, **kwargs):
        super(AbuseChUrlhausPayloadsCollector, self).__init__(*args, **kwargs)
        if not self.config['zip_files_url'].endswith('/'):
            raise ValueError('value of option `zip_files_url` ({!r}) should '
                             '(but does not) end with "/"'.format(self.config['zip_files_url']))
        self._oldest_zip_filename_to_collect = self.config['oldest_zip_filename_to_collect']
        self._newest_zip_filename_to_collect = self.config['newest_zip_filename_to_collect']
        self._state = None                              # to be set in run_handling()
        self._clear_attributes_per_single_zip()

    def _clear_attributes_per_single_zip(self):         # We will set them, respectively:
        self._zip_filename = None                       # - in _handle_zip_filename()
        self._temp_dir = None                           # - in _handle_zip_filename()
        self._archive_http_last_modified = None         # - in _download_and_store_zip_file()
        self._payload_filename_and_info_pairs = None    # - in _obtain_and_prepare_data()

    def run_handling(self):
        LOGGER.info("%s's main activity started", self.__class__.__name__)
        self._state = self._load_state_or_get_default_state()
        for zip_filename in self._iter_uncompleted_zip_filenames():
            self._handle_zip_filename(zip_filename)
        LOGGER.info("%s's main activity finished", self.__class__.__name__)


    def _load_state_or_get_default_state(self):
        state = self.load_state()
        if state is None:
            state = {}
        return state


    def _iter_uncompleted_zip_filenames(self):
        for zip_filename in self._get_valid_and_sorted_zip_filenames():
            if self._state.get(zip_filename) != self.ZIP_COMPLETED_STATUS_TAG:
                yield zip_filename

    def _get_valid_and_sorted_zip_filenames(self):
        LOGGER.info('Valid ZIP filenames will be collected and sorted...')
        all_zip_filenames = self._scrap_all_zip_filenames()
        valid_zip_filenames = list(self._iter_valid_zip_filenames(all_zip_filenames))
        self.ensure_some_zip_filenames_present(valid_zip_filenames)
        valid_zip_filenames.sort()
        LOGGER.info('%s valid zip filenames (within range: "%s" to "%s")'
                    ' - have been collected and sorted. First is "%s" and '
                    'last is "%s".',
                    len(valid_zip_filenames),
                    self._oldest_zip_filename_to_collect,
                    self._newest_zip_filename_to_collect,
                    min(valid_zip_filenames),
                    max(valid_zip_filenames))

        return valid_zip_filenames

    def _scrap_all_zip_filenames(self):
        request_performer = RequestPerformer.fetch(method='GET',
                                                   url=self.config['zip_files_url'],
                                                   retries=self.HTTP_RETRIES)
        zips_page = BeautifulSoup(request_performer, 'html.parser')
        all_zip_names = [href.get('href')
                         for href in zips_page.find_all('a')
                         if href.get('href').endswith(self.ARCHIVE_FILE_EXTENSION)]
        LOGGER.debug('All scrapped ZIP filenames: %r', all_zip_names)
        return all_zip_names

    def _iter_valid_zip_filenames(self, all_zip_filenames):
        for zip_filename in all_zip_filenames:
            if zip_filename in self.config['ignored_zip_filenames']:
                LOGGER.info('Skipping ZIP file whose name %r is '
                            'mentioned in the collector config as '
                            'one of `ignored_zip_filenames`', zip_filename)
                continue
            if not self.VALID_ZIP_FILENAME_REGEX.search(zip_filename):
                LOGGER.warning('Skipping ZIP file whose name %r does not '
                               'match the required pattern', zip_filename)
                continue
            if (self._oldest_zip_filename_to_collect is not None
                    and zip_filename < self._oldest_zip_filename_to_collect):
                continue
            if (self._newest_zip_filename_to_collect is not None
                    and zip_filename > self._newest_zip_filename_to_collect):
                continue
            yield zip_filename

    def ensure_some_zip_filenames_present(self, valid_zip_filenames):
        if not valid_zip_filenames:
            raise ValueError(
                'no valid ZIP filenames found (something wrong with '
                'the site {!r}?!)'.format(self.config['zip_files_url']))


    def _handle_zip_filename(self, zip_filename):
        LOGGER.info('"%s" will be handled...', zip_filename)
        try:
            self._clear_attributes_per_single_zip()
            self._zip_filename = zip_filename
            self._temp_dir = tempfile.mkdtemp(prefix=self.TEMP_DIR_NAME_PREFIX)
            try:
                self._obtain_and_prepare_data()
                self._perform_publishing()
            finally:
                shutil.rmtree(self._temp_dir)
        except:
            LOGGER.error('An exception occurred when handling "%s"', zip_filename)
            raise
        else:
            LOGGER.info('Handling of "%s" finished', zip_filename)


    def _obtain_and_prepare_data(self):
        LOGGER.info('["%s"] Starting obtaining and preparing data...', self._zip_filename)
        zip_url = self._get_zip_url()
        zip_filepath = self._get_zip_filepath()
        unpacked_dir = self._get_unpacked_dir()
        self._download_and_store_zip_file(zip_url, zip_filepath)
        self._unzip_file(zip_filepath, unpacked_dir)
        self._try_to_remove_file(zip_filepath)
        self._payload_filename_and_info_pairs = self._get_payload_filename_and_info_pairs(
                                                                                    unpacked_dir)
        LOGGER.info('["%s"] Obtaining and preparing data finished', self._zip_filename)

    def _get_zip_url(self):
        return '{}{}'.format(self.config['zip_files_url'], self._zip_filename)

    def _get_zip_filepath(self):
        return '{}/{}'.format(self._temp_dir, self._zip_filename)

    def _get_unpacked_dir(self):
        zip_filepath = self._get_zip_filepath()
        unpacked_dir = '{}/'.format(zip_filepath[:-len(self.ARCHIVE_FILE_EXTENSION)])
        return unpacked_dir

    def _download_and_store_zip_file(self, zip_url, zip_filepath):
        with RequestPerformer(method='GET', url=zip_url, retries=self.HTTP_RETRIES) as perf:
            if perf.get_dt_header('Last-Modified'):
                self._archive_http_last_modified = str(perf.get_dt_header('Last-Modified'))
            with open(zip_filepath, 'wb') as f:
                for chunk in perf:
                    f.write(chunk)
        LOGGER.debug('ZIP archive downloaded from %r and stored '
                     'in the %r file', zip_url, zip_filepath)

    def _unzip_file(self, zip_filepath, unpacked_dir):
        at_least_one_extracted = False
        with contextlib.closing(ZipFile(zip_filepath, 'r')) as zipped_file:
            os.mkdir(unpacked_dir)
            for payload_filename in zipped_file.namelist():
                if self.VALID_PAYLOAD_FILENAME_REGEX.search(payload_filename):
                    zipped_file.extract(member=payload_filename,
                                        path=unpacked_dir,
                                        pwd=self.config['zip_file_password'])
                    at_least_one_extracted = True
                    LOGGER.debug('Payload whose filename is %r -- extracted '
                                 'from ZIP archive %r -- into directory %r',
                                 payload_filename, zip_filepath, unpacked_dir)
                else:
                    LOGGER.warning('Payload filename: %r - does not match the required '
                                   'pattern. Containing ZIP file\'s path: %r',
                                   payload_filename, zip_filepath)
        if not at_least_one_extracted:
            raise ValueError(
                'no payload extracted from the {!r} archive (something '
                'wrong with this ZIP file?!)'.format(zip_filepath))

    @staticmethod
    def _try_to_remove_file(filepath):
        try:
            os.remove(filepath)
        except OSError as error:
            LOGGER.warning('Error occurred while trying to remove the file. '
                           '\nFilepath: %r\nError: %r', filepath, error)

    def _get_payload_filename_and_info_pairs(self, unpacked_dir):
        filenames = os.listdir(unpacked_dir)
        payload_filename_and_info_pairs = [(payload_filename,
                                            self._get_payload_info(payload_filename))
                                           for payload_filename in filenames]
        return payload_filename_and_info_pairs

    def _get_payload_info(self, payload_filename):
        # Note: invalid MD5 hash or missing file for a given hash does
        # *not* cause an exception or HTTP-level error; instead, a normal
        # (HTTP-200) response is obtained, though its body contains info
        # about the error.  So such cases are handled later (at the
        # publishing stage).
        api_url = self.config['api_url']
        payload_info = RequestPerformer.fetch(method='POST',
                                              url=api_url,
                                              data={'md5_hash': payload_filename},
                                              retries=self.HTTP_RETRIES)
        LOGGER.debug('Payload info for payload filename %r downloaded from '
                     '%r:\n%r', payload_filename, api_url, payload_info)
        return payload_info


    def _perform_publishing(self):
        LOGGER.info('["%s"] Starting publishing...', self._zip_filename)
        try:
            self.run()
        except:
            LOGGER.info('["%s"] Publishing broken by exception...', self._zip_filename)
            self.stop()
            raise
        else:
            LOGGER.info('["%s"] Publishing finished', self._zip_filename)
        finally:
            self.clear_amqp_communication_state_attributes()


    def stop(self):
        try:
            super(AbuseChUrlhausPayloadsCollector, self).stop()
        except Exception:
            LOGGER.error("Exception occurred when trying to finish activity "
                         "of AMQP connection's IO loop", exc_info=True)

    def start_publishing(self):
        super(AbuseChUrlhausPayloadsCollector, self).start_publishing()
        self.start_iterative_publishing()

    def publish_iteratively(self):
        LOGGER.debug('Iterative publishing started...')
        handled_payload_filenames = self._state.setdefault(self._zip_filename, set())
        assert isinstance(handled_payload_filenames, set)
        this_time_successfully_processed_count = 0
        try:
            for payload_filename, payload_info in self._payload_filename_and_info_pairs:
                payload_filepath = self._get_payload_filepath(payload_filename)
                payload_info_dict = self._get_unhandled_payload_info_dict(
                      payload_filename,
                      payload_info,
                      handled_payload_filenames)
                if payload_info_dict:
                    self._publish(payload_filepath, payload_info_dict)
                    yield self.FLUSH_OUT
                    handled_payload_filenames.add(payload_filename)
                    this_time_successfully_processed_count += 1
                self._try_to_remove_file(payload_filepath)
        except:
            LOGGER.debug('Iterative publishing broken by exception...')
            raise
        finally:
            self._maintain_state(handled_payload_filenames,
                                 this_time_successfully_processed_count)
        LOGGER.debug('Iterative publishing finished')


    def _get_payload_filepath(self, payload_filename):
        return '{}/{}'.format(self._get_unpacked_dir(), payload_filename)

    def _get_unhandled_payload_info_dict(self,
                                         payload_filename,
                                         payload_info,
                                         handled_payload_filenames):
        if payload_filename in handled_payload_filenames:
            return None
        try:
            (query_status,
             payload_info_dict
             ) = self._get_query_status_and_payload_info_dict(payload_filename,
                                                              payload_info)
            self._validate_query_status(payload_filename,
                                        query_status,
                                        handled_payload_filenames)
            self._validate_md5_hash(payload_filename,
                                    payload_info_dict,
                                    handled_payload_filenames)
        except self._PayloadInfoValidationError:
            return None
        return payload_info_dict

    def _get_query_status_and_payload_info_dict(self, payload_filename, payload_info):
        try:
            payload_info_dict = json.loads(payload_info)
            query_status = payload_info_dict['query_status']
        except Exception as exc:
            LOGGER.error('Skipping the payload (this time) because of weird/'
                         'unexpected problem with its info dict (%s). '
                         'Archive filename: "%s". '
                         'Payload filename: "%s".',
                         make_exc_ascii_str(exc),
                         self._zip_filename,
                         payload_filename)
            # note: here we do *not* add `payload_filename`
            # to `handled_payload_filenames` -- so that
            # this payload remains *unhandled*
            raise self._PayloadInfoValidationError
        return query_status, payload_info_dict

    def _validate_query_status(self, payload_filename, query_status, handled_payload_filenames):
        if query_status != 'ok':
            LOGGER.warning('Skipping the payload (permanently!) because of '
                           'invalid `query_status` in its info dict: %r. '
                           'Archive filename: "%s". '
                           'Payload filename: "%s".',
                           query_status,
                           self._zip_filename,
                           payload_filename)
            handled_payload_filenames.add(payload_filename)
            raise self._PayloadInfoValidationError

    def _validate_md5_hash(self, payload_filename, payload_info_dict, handled_payload_filenames):
        md5_hash = payload_info_dict.get('md5_hash')
        if md5_hash is None:
            LOGGER.warning('Skipping the payload (permanently!) because '
                           '`md5_hash` in its info dict is missing or null. '
                           'Archive filename: "%s". '
                           'Payload filename: "%s".',
                           self._zip_filename,
                           payload_filename)
            handled_payload_filenames.add(payload_filename)
            raise self._PayloadInfoValidationError
        if md5_hash != payload_filename:
            LOGGER.error("Skipping the payload (permanently!) because "
                         "`md5_hash` in its info dict (%r) is not equal to "
                         "the payload filename (that's really strange!). "
                         'Archive filename: "%s". '
                         'Payload filename: "%s".',
                         md5_hash,
                         self._zip_filename,
                         payload_filename)
            handled_payload_filenames.add(payload_filename)
            raise self._PayloadInfoValidationError


    def _publish(self, payload_filepath, payload_info_dict):
        payload = read_file(payload_filepath)
        meta_headers = self._get_meta_headers(payload_info_dict)
        (output_rk,
         output_data_body,
         output_prop_kwargs) = self.get_output_components(
            data_body=payload,
            meta_headers=meta_headers)
        self.publish_output(routing_key=output_rk,
                            body=output_data_body,
                            prop_kwargs=output_prop_kwargs)

    def _get_meta_headers(self, payload_info_dict):
        meta_headers = {'tlp': 'white'}
        meta_headers.update(
            self._iter_meta_headers_from_toplevel_items(payload_info_dict))
        firstseen_url = self._get_firstseen_url(payload_info_dict)
        if firstseen_url:
            meta_headers['url'] = firstseen_url
        meta_headers['archive_filename'] = self._zip_filename
        if self._archive_http_last_modified:
            meta_headers['archive_http_last_modified'] = self._archive_http_last_modified
        return meta_headers

    def _iter_meta_headers_from_toplevel_items(self, payload_info_dict):
        for key in self.SAMPLE_EXCHANGE_META_HEADER_KEYS:
            if key in payload_info_dict:
                if payload_info_dict[key] is not None:
                    yield key, payload_info_dict[key]
                else:
                    LOGGER.warning(
                        'Value for meta header key %r is null '
                        '(concerns payload with md5_hash=%r from archive "%s")',
                        key,
                        payload_info_dict['md5_hash'],
                        self._zip_filename)
            else:
                LOGGER.warning(
                    'Missing value for meta header key %r '
                    '(concerns payload with md5_hash=%r from archive "%s")',
                    key,
                    payload_info_dict['md5_hash'],
                    self._zip_filename)

    def _get_firstseen_url(self, payload_info_dict):
        events = payload_info_dict.get('urls')
        if events:
            events_sorted_by_firstseen_and_id = sorted(events,
                                                       key=operator.itemgetter('firstseen',
                                                                               'url_id'))
            firstseen_event = events_sorted_by_firstseen_and_id[0]
            return firstseen_event['url']
        return None

    def get_source_channel(self, **processed_data):
        return 'urlhaus-payloads'

    def get_output_data_body(self, **processed_data):
        return processed_data['data_body']

    def get_output_prop_kwargs(self, meta_headers, **processed_data):
        prop_kwargs = super(AbuseChUrlhausPayloadsCollector,
                            self).get_output_prop_kwargs(**processed_data)
        prop_kwargs['headers'].setdefault('meta', dict())
        prop_kwargs['headers']['meta'].update(meta_headers)
        return prop_kwargs


    def _maintain_state(self, handled_payload_filenames, this_time_successfully_processed_count):
        try:
            unhandled_count = self._get_unhandled_count(handled_payload_filenames)
            self._update_state(handled_payload_filenames, unhandled_count)
        finally:
            self.save_state(self._state)
        self._log_processing_status(handled_payload_filenames,
                                    this_time_successfully_processed_count,
                                    unhandled_count)

    def _get_unhandled_count(self, handled_payload_filenames):
        payload_filenames = {payload_filename
                             for payload_filename, _ in self._payload_filename_and_info_pairs}
        unhandled_count = len(payload_filenames - handled_payload_filenames)
        return unhandled_count

    def _update_state(self, handled_payload_filenames, unhandled_count):
        if unhandled_count == 0:
            self._state[self._zip_filename] = self.ZIP_COMPLETED_STATUS_TAG
            assert handled_payload_filenames  # already checked (see: `_unzip_file()`)
        else:
            assert self._state[self._zip_filename] is handled_payload_filenames

    def _log_processing_status(self,
                               handled_payload_filenames,
                               this_time_successfully_processed_count,
                               unhandled_count):
        if this_time_successfully_processed_count == 0:
            LOGGER.error('This time, *none* of the payloads from the '
                         '"%s" archive could be processed successfully!',
                         self._zip_filename)
        if unhandled_count == 0:
            LOGGER.info('General status of archive "%s" (*final*): '
                        'all %s payloads handled (i.e., processed '
                        'successfully or skipped permanently)',
                        self._zip_filename,
                        len(handled_payload_filenames))
        else:
            LOGGER.warning('General status of archive "%s" (*up to now*): '
                           '%s payloads handled (i.e., processed '
                           'successfully or skipped permanently); '
                           '%s payloads left unhandled (because '
                           'of weird/unexpected problems)',
                           self._zip_filename,
                           len(handled_payload_filenames),
                           unhandled_count)



entry_point_factory(sys.modules[__name__])

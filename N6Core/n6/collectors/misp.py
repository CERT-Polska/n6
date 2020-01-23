# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
Generic MISP collector.
"""

import json
import sys
import time
from collections import (
    deque,
    MutableMapping,
)
from datetime import (
    timedelta,
    datetime,
)
from urlparse import urljoin

from pymisp import (
    PyMISP,
    __version__ as pymisp_version,
)
import requests

from n6.collectors.generic import (
    BaseCollector,
    CollectorWithStateMixin,
    entry_point_factory,
)
from n6lib.common_helpers import exiting_on_exception
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class NoNewEventsException(Exception):
    pass


class SampleDownloadFailure(Exception):
    pass


class MispCollector(CollectorWithStateMixin, BaseCollector):

    output_queue = [
        {
            'exchange': 'raw',
            'exchange_type': 'topic',
        },
        {
            'exchange': 'sample',
            'exchange_type': 'topic',
        },
    ]

    type = 'stream'
    content_type = "application/json"
    config_required = ("source",
                       "misp_url",
                       "misp_key",
                       "cache_dir",
                       "days_for_first_run")

    # a list of sample details' keys included in a message's headers
    sample_message_headers = [
        'category',
        'comment',
        'uuid',
        'event_id',
        'timestamp',
        'to_ids',
        'value',
        'distribution',
        'type',
        'id',
    ]
    # part of the MISP URL to the attributes' files
    default_sample_path = '/attributes/downloadAttachment/download/'

    allowed_tlp_vals = (
        'red',
        'amber',
        'green',
        'white',
    )
    min_tlp_key_name = 'minimum_tlp'

    def __new__(cls, **kwargs):
        self = super(MispCollector, cls).__new__(cls, **kwargs)
        MispCollector.config_group = self.cmdline_args.n6config_section_name
        return self

    def __init__(self, **kwargs):
        super(MispCollector, self).__init__(**kwargs)
        self._now = datetime.now().replace(microsecond=0)
        self._state = self._load_state_or_get_default()
        self._last_events_publishing_datetime = self._state['events_publishing_datetime']
        self._last_samples_publishing_datetime = self._state['samples_publishing_datetime']
        if self._last_samples_publishing_datetime < self._last_events_publishing_datetime:
            self._overdue_samples_to_publish = True
        else:
            self._overdue_samples_to_publish = False
        self._establish_connection()
        self._publishing_samples = False
        self._callback_timeout = int(self.config.get('callback_timeout', 1))
        self._misp_events = None
        self._misp_raw_events = None
        self._output_components = None
        self._samples = None
        self._possible_attribute_types = ['malware-sample']
        sample_path = self.config.get('sample_path', self.default_sample_path)
        self._attributes_url = urljoin(self.config['misp_url'], sample_path)

    # initial methods
    def run(self):
        try:
            self._misp_events = self.get_output_components()
        except NoNewEventsException:
            self._state['events_publishing_datetime'] = self._now
            self.save_state(self._state)
            if self._overdue_samples_to_publish:
                LOGGER.info('No new events, but there are overdue malware samples to publish.')
                super(MispCollector, self).run()
            else:
                LOGGER.info('No new events nor malware samples, closing the collector.')
                self._set_samples_state_to_completed()
        else:
            super(MispCollector, self).run()

    def _load_state_or_get_default(self):
        state = self.load_state()
        if not state or not isinstance(state, MutableMapping):
            _days = int(self.config['days_for_first_run'])
            initial_datetime = self._now - timedelta(days=_days)
            return dict(
                events_publishing_datetime=initial_datetime,
                samples_publishing_datetime=initial_datetime,
                last_published_samples=[],
            )
        else:
            assert state['samples_publishing_datetime'] <= state['events_publishing_datetime'], (
                "Datetime of the last publishing of samples has to be equal or smaller "
                "than a datetime of publishing of the events.")
        return state

    def _set_samples_state_to_completed(self):
        """
        Set the state of publishing of malware samples, as if
        it is completed. Set the datetime to the current time
        and date and clear the list of published samples.
        """
        self._state['samples_publishing_datetime'] = self._now
        del self._state['last_published_samples'][:]
        self.save_state(self._state)

    def _convert_datetime_to_timestamp(self, datetime_):
        dif_time = (self._now - datetime_).total_seconds()/60+15
        return '{:.0f}m'.format(dif_time)

    def get_arg_parser(self):
        arg_parser = super(MispCollector, self).get_arg_parser()
        arg_parser.add_argument(
            'n6config_section_name',
            help='the config section name specific to the chosen MISP collector, e.g.: misp_circl')
        return arg_parser

    def _establish_connection(self):
        misp_url = self.config['misp_url']
        misp_key = self.config['misp_key']
        misp_verifycert = self.get_misp_verifycert()
        self.misp = PyMISP(url=misp_url, key=misp_key, ssl=misp_verifycert)

    # scheduling and publishing methods
    @exiting_on_exception
    def start_publishing(self):
        """
        Schedule publishing of MISP events or downloading of
        the overdue samples.
        """
        if self._misp_events:
            self._schedule(self._do_publish_events)
        else:
            self._schedule(self._prepare_and_schedule_samples_publishing)

    def _prepare_request_headers(self):
        return {'content-type': 'application/zip',
                'Accept': 'application/json',
                'Authorization': self.config['misp_key'],
                'User-Agent': 'PyMISP {} - Python {}.{}.{}'.format(pymisp_version,
                                                                   *sys.version_info)}

    def _schedule(self, meth):
        """
        Add a callback method to the IOLoop timer.

        Args:
            `meth`:
                method passed as a callback for Pika's connection
                add_timeout() method.
        """
        if self._closing:
            LOGGER.warning(
                'Collector %r is being closed so %r will *not* be scheduled', self, meth)
            return
        self._connection.add_timeout(self._callback_timeout, exiting_on_exception(meth))

    def _next_download(self):
        """
        If available, take details about the next malware sample
        and try to download it.

        Raises:
            `SampleDownloadFailure` exception if a sample could not
            be downloaded.
        """
        try:
            self._current_sample = self._samples.popleft()
        except IndexError:
            # an empty list of the last published samples indicates,
            # that all of the samples have been published
            self._set_samples_state_to_completed()
            self.inner_stop()
        else:
            try:
                self._output_components = self.get_output_components()
            except SampleDownloadFailure:
                LOGGER.warning("Cannot download sample with ID: %s.", self._current_sample['id'])
                self._schedule(self._next_download)
            else:
                self._schedule(self._do_publish)

    def _do_publish_events(self):
        """
        Publish MISP events, save the state. Extract details about
        malware samples and proceed to prepare malware samples
        downloading and publishing.
        """
        self.publish_output(*self._misp_events)
        # update a state of the MISP events publishing
        self._state['events_publishing_datetime'] = self._now
        self.save_state(self._state)
        self._schedule(self._prepare_and_schedule_samples_publishing)

    def _do_publish(self):
        """Publish a malware sample through the 'sample' exchange."""
        self.publish_output(*self._output_components, exchange=self.output_queue[1]['exchange'])
        self._output_components = None
        self._state['last_published_samples'].append(int(self._current_sample['id']))
        self.save_state(self._state)
        self._schedule(self._next_download)

    def _prepare_and_schedule_samples_publishing(self):
        """
        Check, whether the 'sample' exchange was declared. Set proper
        flags and attributes.
        """
        sample_exchange = self.output_queue[1]['exchange']
        if sample_exchange in self._declared_output_exchanges:
            # an output queue may be declared here
            try:
                self._samples = deque(self._get_samples_details())
            except NoNewEventsException:
                if self._overdue_samples_to_publish:
                    LOGGER.warning('Datetime of the last publishing of malware samples '
                                   'indicated, that there are overdue samples to publish '
                                   'since the datetime. Although, there are no events and '
                                   'no associated malware samples to download from '
                                   'the saved datetime.')
                else:
                    LOGGER.info('There are no malware samples associated with downloaded events.')
                self._set_samples_state_to_completed()
                self.inner_stop()
            else:
                if self._samples:
                    self._set_attributes_for_samples()
                    self._schedule(self._next_download)
                else:
                    LOGGER.info('No malware samples to publish since: %s',
                                self._state['samples_publishing_datetime'])
                    self._set_samples_state_to_completed()
                    self.inner_stop()
        else:
            LOGGER.error("Exchange '%s' was not declared. Not publishing malware samples.",
                         sample_exchange)
            self.inner_stop()

    # methods determining properties and attributes
    def get_source_channel(self, **kwargs):
        return 'misp'

    def get_output_prop_kwargs(self, *args, **kwargs):
        """
        Method extended in order to include the minimal TLP value
        for an event, inside message's headers, if it was set
        in a config, and malware sample's details, if it is currently
        being published.

        Returns:
            A dict containing message's properties, with minimal
            TLP value or malware sample's additional details.
        """
        properties = super(MispCollector, self).get_output_prop_kwargs(*args, **kwargs)
        min_tlp = self._get_min_tlp()
        if min_tlp:
            properties['headers'].setdefault('meta', dict())[self.min_tlp_key_name] = min_tlp
        if self._publishing_samples:
            properties['headers'].setdefault('meta', dict()).setdefault('misp', dict()).update(
                self._get_sample_headers())
        return properties

    def _get_sample_headers(self):
        """
        Extract the relevant keys from malware sample's details.

        Returns:
            A dict with a relevant data about a sample.
        """
        return {key: self._current_sample[key] for
                key in self.sample_message_headers if key in self._current_sample}

    def _set_attributes_for_samples(self):
        self._publishing_samples = True
        self.type = 'file'

    # downloading methods
    def get_output_data_body(self, source, **processed_data):
        """
        Overridden method fetches MISP events or a malware
        sample's binary data, if the flag is set.
        """
        if not self._publishing_samples:
            return self._get_misp_events(self._state['events_publishing_datetime'])
        sample_id = self._current_sample['id']
        sample_url = urljoin(self._attributes_url, sample_id)
        return self._download_sample(sample_url)

    def _download_sample(self, url):
        """
        Try to download a malware sample from an URL during
        the established timeout.

        Args:
            `url`:
                The URL to the current malware sample.

        Returns:
            A binary data of the sample.

        Raises:
            A `SampleDownloadFailure` if the sample does not exists,
            or it could not be downloaded.
        """
        headers = self._prepare_request_headers()
        timeout = int(self.config['download_timeout'])
        retry_sleep_time = int(self.config['retry_sleep_time'])
        duration = 0
        start_time = datetime.utcnow()
        while duration < timeout:
            response = requests.get(url, headers=headers)
            if response.status_code == 404:
                LOGGER.warning('The URL: %s does not provide a malware sample (status code: 404).',
                               url)
                raise SampleDownloadFailure
            if response.status_code == 200 and response.content:
                break
            LOGGER.info("Failure downloading URL: %s. Status code: %s. Retrying in: %s seconds.",
                        url,
                        response.status_code,
                        retry_sleep_time)
            time.sleep(retry_sleep_time)
            duration = (datetime.utcnow() - start_time).seconds
        else:
            LOGGER.warning("Timeout exceeded, failure downloading URL: %s.", url)
            raise SampleDownloadFailure
        LOGGER.debug('Downloaded a sample from the URL: %s.', url)
        return response.content

    def _get_misp_events(self, initial_datetime):
        """
        Download the events since the established datetime.

        Returns:
            Downloaded events, serialized to a JSON.

        Raises:
            A 'NoNewEventsException' if the source does not provide
            new events.
        """
        initial_timestamp = self._convert_datetime_to_timestamp(initial_datetime)
        data = self.misp.download_last(initial_timestamp).get('response')
        if data:
            self._misp_raw_events = data
            return json.dumps(data)
        raise NoNewEventsException

    # helper methods
    def _get_samples_details(self):
        """
        Get the details of the attributes with a type corresponding
        to the malware samples.

        Args:
            `misp_raw_events` (list):
                A list of the events, before serialization.

        Yields:
            Details of a single malware sample.
        """
        if self._overdue_samples_to_publish:
            self._misp_raw_events = None
            self._get_misp_events(self._state['samples_publishing_datetime'])
            LOGGER.info('Preparing to fetch and publish malware samples, including the overdue '
                        'samples since: %s.', self._state['samples_publishing_datetime'])
        else:
            LOGGER.debug('Preparing to fetch and publish the new malware samples since: %s',
                         self._state['samples_publishing_datetime'])
        raw_events = self._misp_raw_events
        attribute_lists = (x['Event']['Attribute'] for x in raw_events)
        for attr_list in attribute_lists:
            for attr in attr_list:
                if attr['type'] in self._possible_attribute_types and 'id' in attr:
                    if (not self._state['last_published_samples'] or
                            (self._state['last_published_samples'] and
                                int(attr['id']) not in self._state['last_published_samples'])):
                        yield attr

    def get_misp_verifycert(self):
        misp_verifycert = self.config.get('misp_verifycert')
        if not misp_verifycert or misp_verifycert.lower() not in ('false', 'f', 'no', 'n', 'off',
                                                                  '0'):
            return True
        else:
            return False

    def _get_min_tlp(self):
        """
        Get the minimal TLP value for the publishing events
        from a config, if it was set.

        Returns:
            A verified and normalized TLP value.
        """
        min_tlp = self.config.get(self.min_tlp_key_name)
        if min_tlp:
            min_tlp_normalized = min_tlp.lower()
            if min_tlp_normalized in self.allowed_tlp_vals:
                return min_tlp_normalized
            LOGGER.warning("Invalid minimal TLP value: '%s'.", min_tlp)
        return None


entry_point_factory(sys.modules[__name__])

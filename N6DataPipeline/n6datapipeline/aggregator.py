# Copyright (c) 2013-2021 NASK. All rights reserved.

import collections
import pickle
import datetime
import json
import os
import os.path

from n6datapipeline.base import (
    LegacyQueuedBase,
    n6QueueProcessingException,
)
from n6lib.common_helpers import open_file
from n6lib.config import ConfigMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.record_dict import RecordDict


LOGGER = get_logger(__name__)


# in hours, time to wait for the next event before suppressed event is generated
AGGREGATE_WAIT = 12

# in hours, when the source is considered inactive (cleanup should be triggered)
SOURCE_INACTIVITY_TIMEOUT = 24

# in seconds, tick between checks of inactive sources
TICK_TIMEOUT = 3600


class HiFreqEventData:

    def __init__(self, payload):
        self.group = payload.get('_group')
        self.until = parse_iso_datetime_to_utc(payload.get('time'))
        self.first = parse_iso_datetime_to_utc(payload.get('time'))
        self.count = 1  # XXX: see ticket #6243
        self.payload = payload

    def to_dict(self):
        result = self.payload
        result['count'] = self.count
        result['until'] = str(self.until)
        result['_first_time'] = str(self.first)
        return result

    def update_payload(self, update_dict):
        tmp = self.payload.copy()
        tmp.update(update_dict)
        self.payload = tmp


class SourceData:

    def __init__(self, time_tolerance):
        self.time = None  # current time tracked for source (based on event time)
        # utc time of the last event (used to trigger cleanup if source is inactive)
        self.last_event = None
        self.groups = collections.OrderedDict()  # groups aggregated for a given source
        self.time_tolerance = datetime.timedelta(seconds=time_tolerance)
        # buffer to store aggregated events until time_tolerance has passed
        self.buffer = collections.OrderedDict()

    def update_time(self, event_time):
        if event_time > self.time:
            self.time = event_time
        self.last_event = datetime.datetime.utcnow()

    def process_event(self, data):
        event_time = parse_iso_datetime_to_utc(data['time'])
        event = self.groups.get(data['_group'])
        if self.time is None:
            self.time = event_time
        if event_time + self.time_tolerance < self.time:
            if event is None or event.first > event_time:
                LOGGER.error('Event out of order. Ignoring. Data: %s', data)
                raise n6QueueProcessingException('Event out of order.')
            else:
                LOGGER.info('Event out of order, but not older than group\'s first event, '
                            'so it will be added to existing aggregate group. Data: %s', data)
                event.until = max(event.until, event_time)
                event.count += 1  # XXX: see ticket #6243
                return False

        if event is None:
            if event_time < self.time:
                # unordered event, self.buffer may contain suppressed event
                LOGGER.debug("Unordered event of the '%s' group, '%s' source within time "
                             "tolerance. Check and update buffer.", data['_group'], data['source'])
                buffered_event = self.buffer.get(data['_group'])
                if buffered_event is not None:
                    buffered_event.count += 1  # XXX: see ticket #6243
                    self.buffer[data['_group']] = buffered_event
                    return False
            # Event not seen before - add new event to group
            LOGGER.debug("A new group '%s' for '%s' source began to be aggregated, "
                         "first event is being generated.", data['_group'], data['source'])
            self.groups[data['_group']] = HiFreqEventData(data)  # XXX: see ticket #6243
            self.update_time(parse_iso_datetime_to_utc(data['time']))
            return True

        if (event_time > event.until + datetime.timedelta(hours=AGGREGATE_WAIT) or
                event_time.date() > self.time.date()):
            LOGGER.debug("A suppressed event is generated for the '%s' group of "
                         "'%s' source due to passing of %s hours between events.",
                         data['_group'], data['source'], AGGREGATE_WAIT)
            # 24 hour aggregation or AGGREGATE_WAIT time passed between events in group
            del self.groups[data['_group']]
            self.groups[data['_group']] = HiFreqEventData(data)  # XXX: see ticket #6243
            self.buffer[data['_group']] = event
            self.update_time(parse_iso_datetime_to_utc(data['time']))
            return True

        # Event for existing group and still aggregating
        LOGGER.debug("Event is being aggregated in the '%s' group of the '%s' source.",
                     data['_group'], data['source'])
        event.count += 1  # XXX: see ticket #6243
        if event_time > event.until:
            event.until = event_time
        del self.groups[data['_group']]
        self.groups[data['_group']] = event
        self.update_time(parse_iso_datetime_to_utc(data['time']))
        return False

    def generate_suppressed_events(self):
        cutoff_time = self.time - datetime.timedelta(hours=AGGREGATE_WAIT)
        cutoff_check_complete = False
        for_cleanup = []
        for k, v in self.groups.items():
            if v.until >= cutoff_time:
                cutoff_check_complete = True
            if cutoff_check_complete and v.until.date() == self.time.date():
                break
            for_cleanup.append(k)
            self.buffer[k] = v
            # yield 'suppressed', v.to_dict() if v.count > 1 else None
        for k in for_cleanup:
            del self.groups[k]

        # generate suppressed events from buffer
        cutoff_time = self.time - self.time_tolerance
        for_cleanup = []
        for k, v in self.buffer.items():
            if v.until >= cutoff_time:
                break
            for_cleanup.append(k)
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        for k in for_cleanup:
            del self.buffer[k]

    def generate_suppressed_events_after_inactive(self):
        for _, v in self.buffer.items():
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        for _, v in self.groups.items():
            # XXX: see ticket #6243 (check whether here is OK or also will need to be changed)
            yield 'suppressed', v.to_dict() if v.count > 1 else None
        self.groups.clear()
        self.buffer.clear()
        self.last_event = datetime.datetime.utcnow()

    def __repr__(self):
        return repr(self.groups)


class AggregatorData:

    def __init__(self):
        self.sources = {}

    def get_or_create_sourcedata(self, event, time_tolerance):
        source = event['source']
        sd = self.sources.get(source)
        if sd is None:
            sd = SourceData(time_tolerance)
            self.sources[source] = sd
        return sd

    def get_sourcedata(self, event):
        # event['source'] exists because it was created in
        # `Aggregator.process_event()` where `process_new_message(data)`
        # is run before `generate_suppresed_events_for_source(data)`.
        return self.sources[event['source']]

    def __repr__(self):
        return repr(self.sources)


class AggregatorDataWrapper:

    def __init__(self, dbpath, time_tolerance, time_tolerance_per_source):
        self.aggr_data = None
        self.dbpath = dbpath
        self.time_tolerance = time_tolerance
        self.time_tolerance_per_source = time_tolerance_per_source
        try:
            self.restore_state()
        except:
            LOGGER.error('Error restoring state from: %a', self.dbpath)
            self.aggr_data = AggregatorData()

    def store_state(self):
        try:
            with open_file(self.dbpath, 'wb') as f:
                pickle.dump(self.aggr_data, f, protocol=2)
        except IOError:
            LOGGER.error('Error saving state to: %a', self.dbpath)

    def restore_state(self):
        with open_file(self.dbpath, 'rb') as f:
            self.aggr_data = pickle.load(f)

    def process_new_message(self, data):
        """
        Processes a message and validates agains db to detect suppressed
        event.
        Adds new entry to db if necessary (new) or updates entry.

        Returns:
            True: when first event in the group received
                  (i.e. should not be suppressed)
            False: when next event in group received
                   (i.e. should be suppressed and count updated)
        """

        source_data = self.aggr_data.get_or_create_sourcedata(
            data,
            self.time_tolerance_per_source.get(data['source']) or self.time_tolerance,
        )
        result = source_data.process_event(data)
        return result

    def generate_suppresed_events_for_source(self, data):
        """
        Called after each event in a given source was processed.
        Yields suppressed events.
        """
        source_data = self.aggr_data.get_sourcedata(data)
        for event in source_data.generate_suppressed_events():
            yield event

    def generate_suppresed_events_after_timeout(self):
        """Scans all stored sources and based on real time
         (i.e. source has been inactive for defined time)
        generates suppressed events for inactive sources
        """
        LOGGER.debug('Detecting inactive sources after tick timout')
        time_now = datetime.datetime.utcnow()
        for source in self.aggr_data.sources.values():
            LOGGER.debug('Checking source: %a', source)
            if source.last_event + datetime.timedelta(hours=SOURCE_INACTIVITY_TIMEOUT) < time_now:
                LOGGER.debug('Source inactive. Generating suppressed events')
                for type_, event in source.generate_suppressed_events_after_inactive():
                    LOGGER.debug('%a: %a', type_, event)
                    yield type_, event


class Aggregator(ConfigMixin, LegacyQueuedBase):

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
        'queue_name': 'aggregator',
        'accepted_event_types': [
            'hifreq',
        ],
    }
    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    config_spec = '''
        [aggregator]
        dbpath
        time_tolerance :: int
        time_tolerance_per_source = {} :: json
    '''

    def __init__(self, **kwargs):
        self.aggregator_config = self.get_config_section()
        dbpath_dirname = os.path.dirname(self.aggregator_config['dbpath'])
        try:
            os.makedirs(dbpath_dirname, 0o700)
        except OSError:
            pass
        super(Aggregator, self).__init__(**kwargs)
        # store dir doesn't exist, stop aggregator
        if not os.path.isdir(dbpath_dirname):
            raise Exception('store dir does not exist, stop aggregator, path:',
                            self.aggregator_config['dbpath'])
        # store directory exists, but it has no rights to write
        if not os.access(dbpath_dirname, os.W_OK):
            raise Exception('stop aggregator, remember to set the rights'
                            ' for user, which runs aggregator,  path:',
                            self.aggregator_config['dbpath'])
        self.db = AggregatorDataWrapper(self.aggregator_config['dbpath'],
                                        self.aggregator_config['time_tolerance'],
                                        self.aggregator_config['time_tolerance_per_source'])
        self.timeout_id = None   # id of the 'tick' timeout that executes source cleanup

    def start_publishing(self):
        """
        Called on startup.
        Processes data from db and generates new timeouts for remaining
        entries.
        """
        self.set_timeout()

    def on_timeout(self):
        """
        Callback called periodically after given timeout.
        """
        LOGGER.debug('Tick passed')
        for type_, event in self.db.generate_suppresed_events_after_timeout():
            if event is not None:
                self.publish_event((type_, event))
        self.set_timeout()

    def process_event(self, data):
        """
        Processes the event aggregation.
        Each event also triggers additional suppressed events based
        on time of the given source.
        """
        do_publish_new_message = self.db.process_new_message(data)
        if do_publish_new_message:
            self.publish_event(('event', data))
        for type_, event in self.db.generate_suppresed_events_for_source(data):
            if event is not None:
                self.publish_event((type_, event))

    # XXX: can be removed after resolving ticket #6324
    @staticmethod
    def _clean_count_related_stuff(cleaned_payload):
        count_max = RecordDict.data_spec.count.max_value
        count = cleaned_payload.get('count', 1)
        if count > count_max:
            cleaned_payload['count_actual'] = count
            cleaned_payload['count'] = count_max

    def _get_cleaned_payload(self, type_, payload):
        cleaned_payload = payload.copy()
        cleaned_payload['type'] = type_
        cleaned_payload.pop('_group', None)
        self._clean_count_related_stuff(cleaned_payload)
        return cleaned_payload

    def publish_event(self, data):
        """Publishes event to the output queue"""
        type_, payload = data
        if type_ is None:
            return
        cleaned_payload = self._get_cleaned_payload(type_, payload)
        source, channel = cleaned_payload['source'].split('.')
        rk = "{}.{}.{}.{}".format(type_, "aggregated", source, channel)
        body = json.dumps(cleaned_payload)
        self.publish_output(routing_key=rk, body=body)

    def set_timeout(self):
        LOGGER.debug('Setting tick timeout')
        self.timeout_id = self._connection.add_timeout(TICK_TIMEOUT, self.on_timeout)

    def input_callback(self, routing_key, body, properties):
        record_dict = RecordDict.from_json(body)
        with self.setting_error_event_info(record_dict):
            data = dict(record_dict) ## FIXME?: maybe it could be just the record_dict?
            if '_group' not in data:
                raise n6QueueProcessingException("Hi-frequency source missing '_group' field.")
            self.process_event(data)

    def stop(self):
        self.db.store_state()
        super(Aggregator, self).stop()


def main():
    with logging_configured():
        if os.environ.get('n6integration_test'):
            # for debugging only
            import logging
            import sys
            LOGGER.setLevel(logging.DEBUG)
            LOGGER.addHandler(logging.StreamHandler(stream=sys.__stdout__))
        a = Aggregator()
        try:
            a.run()
        except KeyboardInterrupt:
            a.stop()


if __name__ == '__main__':
    main()

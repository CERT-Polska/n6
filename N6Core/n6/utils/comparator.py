# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import json
import cPickle
import os
import os.path

from n6lib.config import Config
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger, logging_configured
from n6.base.queue import (
    QueuedBase,
    n6QueueProcessingException,
)


LOGGER = get_logger(__name__)


class BlackListData(object):
    
    def __init__(self, payload):
        self.id = payload.get("id")
        self.source = payload.get("source")
        self.url = payload.get("url")
        self.fqdn = payload.get("fqdn")
        self.ip = [str(addr["ip"]) for addr in payload.get("address")] if payload.get("address") is not None else []
        self.flag = payload.get("flag")
        self.expires = parse_iso_datetime_to_utc(payload.get("expires"))
        self.payload = payload.copy()
        
    def to_dict(self):
        return self.payload
    
    def update_payload(self, update_dict):
        tmp = self.payload.copy()
        tmp.update(update_dict)
        self.payload = tmp


class SourceData(object):

    def __init__(self):
        self.time = None  # current time tracked for source (based on event _bl-time)
        # real time of the last event (used to trigger cleanup if source is inactive)
        self.last_event = None
        self.blacklist = {}  # current state of black list

    def update_time(self, event_time):
        if event_time > self.time:
            self.time = event_time
        self.last_event = datetime.datetime.now()  ## FIXME unused variable ?

    def _are_ips_different(self, ips_old, ips_new):
        """
        Compare lists of ips.
        
        Returns:
            True if lists different
            False if lists the same
        """
        if ips_old is None and ips_new is None:
            return False
        if (ips_old is None and ips_new is not None) or (ips_old is not None and ips_new is None):
            return True
        if sorted(ips_old) == sorted(ips_new):
            return False
        else:
            return True
        
    def get_event_key(self, data):
        if data.get("url") is not None:
            return data.get("url")
        elif data.get("fqdn") is not None:
            return data.get("fqdn")
        elif data.get("address") is not None:
            ips = tuple(sorted([str(addr["ip"]) for addr in data.get("address")]))
            return ips
        else:
            raise n6QueueProcessingException('Unable to determine event key for source: {}. Event '
                                             'must have at least one of `url`, `fqdn`, '
                                             '`address`, data: {}'.format(data['source'], data) )

    def process_event(self, data):
        event_time = parse_iso_datetime_to_utc(data['_bl-time'])

        if self.time is None:
            self.time = event_time
        if event_time < self.time:
            LOGGER.error('Event out of order. Ignoring.\nData: %s', data)
            raise n6QueueProcessingException('Event belongs to blacklist'
                                             ' older than the last one processed.')

        event_key = self.get_event_key(data)
        event = self.blacklist.get(event_key)

        if event is None:
            # new bl event
            new_event = BlackListData(data)
            new_event.flag = data.get("_bl-series-id")
            self.blacklist[event_key] = new_event
            return 'bl-new', new_event.payload
        else:
            # existing
            ips_old = event.ip
            ips_new = [x["ip"] for x in data.get("address")] if data.get("address") is not None else []
            if self._are_ips_different(ips_old, ips_new):
                data["replaces"] = event.id
                new_event = BlackListData(data)
                new_event.flag = data.get("_bl-series-id")
                self.blacklist[event_key] = new_event
                return "bl-change", new_event.payload
            elif parse_iso_datetime_to_utc(data.get("expires")) != event.expires:
                event.expires = parse_iso_datetime_to_utc(data.get("expires"))
                event.flag = data.get("_bl-series-id")
                event.update_payload({"expires": data.get("expires")})
                self.blacklist[event_key] = event
                return "bl-update", event.payload
            else:
                event.flag = data.get("_bl-series-id")
                self.blacklist[event_key] = event
                return None, event.payload

    def process_deleted(self):

        ret_value = []
        for key, event in list(self.blacklist.iteritems()):
            if event.flag is None:
                value = event.payload.copy()
                if key in self.blacklist:
                    del self.blacklist[key]
                # yield "bl-delist", value
                ret_value.append(["bl-delist", value])
                continue
            if event.expires < self.time:
                value = event.payload.copy()
                if key in self.blacklist:
                    del self.blacklist[key]
                # yield "bl-expire", value
                ret_value.append(["bl-expire", value])
                continue
            event.flag = None
        return ret_value

    def clear_flags(self, flag_id):
        for key, event in list(self.blacklist.iteritems()):
            if event.flag == flag_id:
                event.flag = None
                self.blacklist[key] = event

    def __repr__(self):
        return repr(self.groups)


class ComparatorData(object):

    def __init__(self):
        self.sources = {}

    def get_or_create_sourcedata(self, source_name):
        sd = self.sources.get(source_name)
        if sd is None:
            sd = SourceData()
            self.sources[source_name] = sd
        return sd

    def __repr__(self):
        return repr(self.sources)


class ComparatorDataWrapper(object):

    def __init__(self, dbpath):
        self.comp_data = None
        self.dbpath = dbpath
        try:
            self.restore_state()
        except:
            LOGGER.error("Error restoring state from: %r", self.dbpath)
            self.comp_data = ComparatorData()

    def store_state(self):
        try:
            with open(self.dbpath, "w") as f:
                cPickle.dump(self.comp_data, f)
        except IOError:
            LOGGER.error("Error saving state to: %r", self.dbpath)

    def restore_state(self):
        with open(self.dbpath, "r") as f:
            self.comp_data = cPickle.load(f)

    def process_new_message(self, data):
        """Processes a message and validates agains db to detect new/change/update.
        Adds new entry to db if necessary (new) or updates entry (change/update) and
        stores flag in db for processed event.
        """
        source_data = self.comp_data.get_or_create_sourcedata(data['source'])
        result = source_data.process_event(data)
        source_data.update_time(parse_iso_datetime_to_utc(data['_bl-time']))
        return result

    def clear_flags(self, source, flag_id):
        """Cleans up flags in the db after processing complete blacklist
        """
        source_data = self.comp_data.get_or_create_sourcedata(source)
        source_data.clear_flags(flag_id)
        self.store_state()

    def process_deleted(self, source):
        """Finds unflagged and expired messages for a bl_name (deleted) and generates delist/expire messages.
        Removes entries from db.
        """

        source_data = self.comp_data.get_or_create_sourcedata(source)
        for event in source_data.process_deleted():
            yield event
        self.store_state()


class ComparatorState(object):

    def __init__(self, cleanup_time):
        """
        closed_series = {series-id: expires_time, #time.time when the closed series expires and should be removed
                         ...}
        open_series = {series-id: {"total": int, #total number of messages in a series
                                   "msg-count": int #number of messages seen so far
                                   "msg-nums": [int, ...], #message numbers of seen messages
                                   "msg-ids": [str, ...], #ids of the seen messages
                                   "timeout-id": str, #id of the created timeout for a serie
                                    }
                       ...}
        """
        self.open_series = dict()
        self.cleanup_time = cleanup_time

    def is_series_complete(self, series_id):
        """Verify if the series is complete"""
        assert series_id in self.open_series
        if self.open_series[series_id]["total"] == self.open_series[series_id]["msg-count"]:
            return True
        else:
            return False

    def is_message_valid(self, message):
        """Check if message belongs to open series and it was not seen earlier
        (i.e. is not a duplicate)
        """
        if message["_bl-series-id"] in self.open_series:
            #if message["id"] in self.open_series[message["_bl-series-id"]]["msg-ids"]:
            #    return False
            if message["_bl-series-total"] != self.open_series[message["_bl-series-id"]]["total"]:
                return False
            if message["_bl-series-no"] in self.open_series[message["_bl-series-id"]]["msg-nums"]:
                return False
            if self.open_series[message["_bl-series-id"]]["msg-count"] + 1 > self.open_series[message["_bl-series-id"]]["total"]:
                return False
        return True

    def update_series(self, message):
        """Update series state based on message:
        - create new series if necessary
        - update message count for a series
        - store message id and msg num
        """
        if message["_bl-series-id"] not in self.open_series:
            self.open_series[message["_bl-series-id"]] = {"total": int(message["_bl-series-total"]),
                                                         "timeout-id": None,
                                                         "msg-count": 0,
                                                         "msg-nums": [],
                                                         "msg-ids": []
                                                         }
        self.open_series[message["_bl-series-id"]]["msg-count"] += 1
        self.open_series[message["_bl-series-id"]]["msg-nums"].append(int(message["_bl-series-no"]))
        self.open_series[message["_bl-series-id"]]["msg-ids"].append(message["id"])
        # print "received message series %s: %d of %d" % (message["_bl-series-id"],
        #                                                 self.open_series[message["_bl-series-id"]]["msg-count"],
        #                                                 self.open_series[message["_bl-series-id"]]["total"])

    def close_series(self, series_id):
        """Close given series
        """
        assert series_id in self.open_series
        del self.open_series[series_id]

    def save_timeout(self, series_id, timeout_id):
        """Save timeout id for a given series
        """
        assert series_id in self.open_series
        self.open_series[series_id]["timeout-id"] = timeout_id

    def get_timeout(self, series_id):
        """Get timeout id for a given series
        """
        assert series_id in self.open_series
        return self.open_series[series_id]["timeout-id"]


class Comparator(QueuedBase):

    input_queue = {"exchange": "event",
                   "exchange_type": "topic",
                   "queue_name": "comparator",
                   "binding_keys": ["bl.enriched.*.*"]
                   }
    output_queue = {"exchange": "event",
                    "exchange_type": "topic"
                    }

    def __init__(self, **kwargs):
        config = Config(required={"comparator": ("dbpath", "series_timeout", "cleanup_time")})
        self.comparator_config = config["comparator"]
        self.comparator_config["dbpath"] = os.path.expanduser(self.comparator_config["dbpath"])
        try:
            os.makedirs(self.comparator_config["dbpath"], 0700)
        except OSError:
            pass
        super(Comparator, self).__init__(**kwargs)
        # store dir doesn't exist, stop comparator
        if not os.path.isdir(os.path.dirname(self.comparator_config["dbpath"])):
            raise Exception('store dir does not exist, stop comparator,  path:',
                            self.comparator_config["dbpath"])
        # store directory exists, but it has no rights to write
        if not os.access(os.path.dirname(self.comparator_config["dbpath"]),  os.W_OK):
            raise Exception('stop comparator, remember to set the rights'
                            ' for user, which runs comparator,  path:',
                            self.comparator_config["dbpath"])
        self.state = ComparatorState(int(self.comparator_config["cleanup_time"]))
        self.db = ComparatorDataWrapper(self.comparator_config["dbpath"])

    def on_series_timeout(self, source, series_id):
        """Callback called when the messages for a given series have
        not arrived within series_timeout from the last msg.
        Cleans up the flags in the db and closes the series in ComparatorState
        """
        self.db.clear_flags(source, series_id)
        self.state.close_series(series_id)

    def process_event(self, data):
        """Processes the event by querying the blacklist db and generating
        bl-new, bl-change, bl-update messages
        """
        event = self.db.process_new_message(data)
        self.publish_event(event)

    def finalize_series(self, series_id, bl_name):
        """If all the messages for a series have arrived it finalizes the series:
        generates bl-delist, bl-expire messages from db.
        Close the series in ComparatorState
        """
        self.remove_timeout(series_id)
        for event in self.db.process_deleted(bl_name):
            self.publish_event(event)
        self.state.close_series(series_id)

    def _cleanup_data(self, data):
        """Removes artifacts from earlier processing (_bl-series-no, _bl-series-total, _bl-series-id)
        """
        for k in data.keys():
            if k.startswith("_bl-series"):
                del data[k]
        return data

    def publish_event(self, data):
        """Publishes event to the output queue
        """
        type_, payload = data
        if type_ is None:
            return
        payload = self._cleanup_data(payload)
        payload["type"] = type_
        source, channel = payload["source"].split(".")
        rk = "{}.{}.{}.{}".format(type_, "compared", source, channel)
        body = json.dumps(payload)
        self.publish_output(routing_key=rk, body=body)

    def set_timeout(self, source, series_id):
        self.remove_timeout(series_id)
        timeout_id = self._connection.add_timeout(
            int(self.comparator_config['series_timeout']),
            lambda: self.on_series_timeout(source, series_id))
        self.state.save_timeout(series_id, timeout_id)

    def remove_timeout(self, series_id):
        timeout_id = self.state.get_timeout(series_id)
        if timeout_id is not None:
            self._connection.remove_timeout(timeout_id)

    def validate_bl_headers(self, message):
        if ('_bl-series-id' not in message or
              '_bl-series-total' not in message or
              '_bl-series-no' not in message or
              '_bl-time' not in message or
              'expires' not in message):
            raise n6QueueProcessingException("Invalid message for a black list")
        try:
            parse_iso_datetime_to_utc(message["expires"])
        except ValueError:
            raise n6QueueProcessingException("Invalid expiry date")

    def input_callback(self, routing_key, body, properties):
        data = json.loads(body)
        ## FIXME:? ^ shouldn't `data` be deserialized to a
        ##         RecordDict (BLRecordDict) instance? (for consistency etc.)
        with self.setting_error_event_info(data):
            self._process_input(data)

    def _process_input(self, data):
        self.validate_bl_headers(data)
        if not self.state.is_message_valid(data):
            raise n6QueueProcessingException("Invalid message for a series: {}".format(data))
        self.state.update_series(data)
        self.set_timeout(data["source"], data["_bl-series-id"])
        self.process_event(data)
        if self.state.is_series_complete(data["_bl-series-id"]):
            LOGGER.info("Finalizing series: %r", data["_bl-series-id"])
            self.finalize_series(data["_bl-series-id"], data["source"])

    def stop(self):
        self.db.store_state()
        super(Comparator, self).stop()


def main():
    with logging_configured():
        c = Comparator()
        try:
            c.run()
        except KeyboardInterrupt:
            c.stop()


if __name__ == '__main__':
    main()

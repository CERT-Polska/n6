#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 NASK. All rights reserved.

"""
The *recorder* component -- adds n6 events to the database.
"""

### TODO: this module is to be replaced with a new implementation...

import datetime
import logging
import os
import sys

import n6.archiver.mysqldb_patch

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError

from n6.base.queue import QueuedBase
from n6lib.config import Config
from n6lib.data_backend_api import N6DataBackendAPI
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.db_events import n6ClientToEvent, n6NormalizedData
from n6lib.log_helpers import get_logger, logging_configured
from n6lib.record_dict import RecordDict, BLRecordDict
from n6lib.transaction_helpers import transact
from n6lib.common_helpers import replace_segment


### MySQLdb warnings monkey-patching:
### to write to stderr only, set:
# n6.archiver.mysqldb_patch.warning_standard = True
# n6.archiver.mysqldb_patch.warning_details_to_logs = False
### to write to logs only, set:
# n6.archiver.mysqldb_patch.warning_standard = False
# n6.archiver.mysqldb_patch.warning_details_to_logs = True

logging.basicConfig()

## many logs from db:
#logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

LOGGER = get_logger(__name__)


class PublishError(Exception):
    """Exeption used by SourceTransfer class"""


class Recorder(QueuedBase):
    """Save record in zbd queue."""
    input_queue = {"exchange": "event",
                   "exchange_type": "topic",
                   "queue_name": 'zbd',
                   "binding_keys": ['event.filtered.*.*',
                                    'bl-new.filtered.*.*',
                                    'bl-change.filtered.*.*',
                                    'bl-delist.filtered.*.*',
                                    'bl-expire.filtered.*.*',
                                    'bl-update.filtered.*.*',
                                    'suppressed.filtered.*.*',
                                    ]
                   }

    output_queue = {"exchange": "event",
                    "exchange_type": "topic"
                    }

    SQL_WAIT_TIMEOUT = "SET SESSION wait_timeout = {wait}"

    def __init__(self, **kwargs):
        LOGGER.info("Recorder Start")
        config = Config(required={"recorder": ("uri", "echo")})
        self.config = config["recorder"]
        self.rows = None
        self.record_dict = None
        self.source = None
        self.dir_name = None
        self.wait_timeout = int(self.config.get("wait_timeout", 28800))
        engine = create_engine(self.config["uri"], echo=bool((int(self.config["echo"]))))
        self.session_db = N6DataBackendAPI.configure_db_session(engine)
        self.set_session_wait_timeout()
        self.records = None
        self.routing_key = None

        self.dict_map_fun = {
            "event.filtered": (RecordDict.from_json, self.new_event),
            "bl-new.filtered": (BLRecordDict.from_json, self.blacklist_new),
            "bl-change.filtered": (BLRecordDict.from_json, self.blacklist_change),
            "bl-delist.filtered": (BLRecordDict.from_json, self.blacklist_delist),
            "bl-expire.filtered": (BLRecordDict.from_json, self.blacklist_expire),
            "bl-update.filtered": (BLRecordDict.from_json, self.blacklist_update),
            "suppressed.filtered": (RecordDict.from_json, self.suppressed_update),
        }
        # keys in each of the tuples being values of `dict_map_fun`
        self.FROM_JSON = 0
        self.HANDLE_EVENT = 1

        super(Recorder, self).__init__(**kwargs)

    def ping_connection(self):
        """
        Required to maintain the connection to MySQL.
        Perform ping before each query to the database.
        OperationalError if an exception occurs, remove sessions, and connects again.
        Set the wait_timeout(Mysql session variable) for the session on self.wait_timeout.
        """
        try:
            self.session_db.execute("SELECT 1")
        except OperationalError as exc:
            # OperationalError: (2006, 'MySQL server has gone away')
            LOGGER.warning("Database server went away: %r", exc)
            LOGGER.info("Reconnect to server")
            self.session_db.remove()
            self.set_session_wait_timeout()

    def set_session_wait_timeout(self):
        """set session wait_timeout in mysql SESSION  VARIABLES"""
        self.session_db.execute(Recorder.SQL_WAIT_TIMEOUT.format(wait=self.wait_timeout))

    @staticmethod
    def get_truncated_rk(rk, parts):
        """
        Get only a part of the given routing key.

        Args:
            `rk`: routing key.
            `parts`: number of dot-separated parts (segments) to be kept.

        Returns:
            Truncated `rk` (containing only first `parts` segments).

        >>> Recorder.get_truncated_rk('111.222.333.444', 0)
        ''
        >>> Recorder.get_truncated_rk('111.222.333.444', 1)
        '111'
        >>> Recorder.get_truncated_rk('111.222.333.444', 2)
        '111.222'
        >>> Recorder.get_truncated_rk('111.222.333.444', 3)
        '111.222.333'
        >>> Recorder.get_truncated_rk('111.222.333.444', 4)
        '111.222.333.444'
        >>> Recorder.get_truncated_rk('111.222.333.444', 5)  # with log warning
        '111.222.333.444'
        """
        rk = rk.split('.')
        parts_rk = []
        try:
            for i in xrange(parts):
                parts_rk.append(rk[i])
        except IndexError:
            LOGGER.warning("routing key %r contains less than %r segments", rk, parts)
        return '.'.join(parts_rk)

    def input_callback(self, routing_key, body, properties):
        """ Channel callback method """
        # first let's try ping mysql server
        self.ping_connection()
        self.records = {'event': [], 'client': []}
        self.routing_key = routing_key

        # take the first two parts of the routing key
        truncated_rk = self.get_truncated_rk(self.routing_key, 2)

        # run BLRecordDict.from_json() or RecordDict.from_json()
        # depending on the routing key
        from_json = self.dict_map_fun[truncated_rk][self.FROM_JSON]
        self.record_dict = from_json(body)
        # add modified time, set microseconds to 0, because the database
        #  does not have microseconds, and it is not known if the base is not rounded
        self.record_dict['modified'] = datetime.datetime.utcnow().replace(microsecond=0)
        # run the handler method corresponding to the routing key
        handle_event = self.dict_map_fun[truncated_rk][self.HANDLE_EVENT]
        with self.setting_error_event_info(self.record_dict):
            handle_event()

        assert 'source' in self.record_dict
        LOGGER.debug("source: %r", self.record_dict['source'])
        LOGGER.debug("properties: %r", properties)
        #LOGGER.debug("body: %r", body)

    def json_to_record(self, rows):
        """
        Deserialize json to record db.append.

        Args: `rows`: row from RecordDict
        """
        if 'client' in rows[0]:
            for client in rows[0]['client']:
                tmp_rows = rows[0].copy()
                tmp_rows['client'] = client
                self.records['client'].append(tmp_rows)

    def insert_new_event(self, items, with_transact=True, recorded=False):
        """
        New events and new blacklist add to database,
        default in the transaction, or the outer transaction(with_transact=False).
        """
        try:
            if with_transact:
                with transact:
                    self.session_db.add_all(items)
            else:
                self.session_db.add_all(items)
        except IntegrityError as exc:
            LOGGER.warning("IntegrityError %r", exc)
        else:
            if recorded and not self.cmdline_args.n6recovery:
                rk = replace_segment(self.routing_key, 1, 'recorded')
                LOGGER.debug(
                    'Publish for email notifications '
                    '-- rk: %r, record_dict: %r',
                    rk, self.record_dict)
                self.publish_event(self.record_dict, rk)

    def publish_event(self, data, rk):
        """
        Publishes event to the output queue.

        Args:
            `data`: data from recorddict
            `rk`  : routing key
        """
        body = data.get_ready_json()
        self.publish_output(routing_key=rk, body=body)

    def new_event(self, _is_blacklist=False):
        """
        Add new event to n6 database.
        """
        LOGGER.debug('* new_event() %r', self.record_dict)

        # add event records from RecordDict
        for event_record in self.record_dict.iter_db_items():
            if _is_blacklist:
                event_record["status"] = "active"
            self.records['event'].append(event_record)

        self.json_to_record(self.records['event'])
        items = []
        for record in self.records['event']:
            event = n6NormalizedData(**record)
            items.append(event)

        for record in self.records['client']:
            client = n6ClientToEvent(**record)
            items.append(client)

        LOGGER.debug("insert new events, count.: %r", len(items))
        self.insert_new_event(items, recorded=True)

    def blacklist_new(self):
        self.new_event(_is_blacklist=True)

    def blacklist_change(self):
        """
        Black list change(change status to replaced in existing blacklist event,
        and add new event in changing values(new id, and old replaces give comparator)).
        """
        # add event records from RecordDict
        for event_record in self.record_dict.iter_db_items():
            self.records['event'].append(event_record)

        self.json_to_record(self.records['event'])
        id_db = self.records['event'][0]["id"]
        id_replaces = self.records['event'][0]["replaces"]
        LOGGER.debug("ID: %r REPLACES: %r", id_db, id_replaces)

        try:
            with transact:
                rec_count = (self.session_db.query(n6NormalizedData).
                             filter(n6NormalizedData.id == id_replaces).
                             update({'status': 'replaced',
                                     'modified': datetime.datetime.utcnow().replace(microsecond=0)
                                     }))

            with transact:
                items = []
                for record in self.records['event']:
                    record["status"] = "active"
                    event = n6NormalizedData(**record)
                    items.append(event)

                for record in self.records['client']:
                    client = n6ClientToEvent(**record)
                    items.append(client)

                if rec_count:
                    LOGGER.debug("insert new events, count.: %r", len(items))
                else:
                    LOGGER.debug("bl-change, records with id %r DO NOT EXIST!", id_replaces)
                    LOGGER.debug("inserting new events anyway, count.: %r", len(items))
                self.insert_new_event(items, with_transact=False, recorded=True)

        except IntegrityError as exc:
            LOGGER.warning("IntegrityError: %r", exc)

    def blacklist_delist(self):
        """
        Black list delist (change status to delisted in existing blacklist event).
        """
        # add event records from RecordDict
        for event_record in self.record_dict.iter_db_items():
            self.records['event'].append(event_record)

        self.json_to_record(self.records['event'])
        id_db = self.records['event'][0]["id"]
        LOGGER.debug("ID: %r STATUS: %r", id_db, 'delisted')

        with transact:
            (self.session_db.query(n6NormalizedData).
             filter(n6NormalizedData.id == id_db).
             update(
                {
                    'status': 'delisted',
                    'modified': datetime.datetime.utcnow().replace(microsecond=0),
                }))

    def blacklist_expire(self):
        """
        Black list expire (change status to expired in existing blacklist event).
        """
        # add event records from RecordDict
        for event_record in self.record_dict.iter_db_items():
            self.records['event'].append(event_record)

        self.json_to_record(self.records['event'])

        id_db = self.records['event'][0]["id"]
        LOGGER.debug("ID: %r STATUS: %r", id_db, 'expired')

        with transact:
            (self.session_db.query(n6NormalizedData).
             filter(n6NormalizedData.id == id_db).
             update(
                {
                    'status': 'expired',
                    'modified': datetime.datetime.utcnow().replace(microsecond=0),
                }))

    def blacklist_update(self):
        """
        Black list update (change expires to new value in existing blacklist event).
        """
        # add event records from RecordDict
        for event_record in self.record_dict.iter_db_items():
            self.records['event'].append(event_record)

        self.json_to_record(self.records['event'])
        id_event = self.records['event'][0]["id"]
        expires = self.records['event'][0]["expires"]
        LOGGER.debug("ID: %r NEW_EXPIRES: %r", id_event, expires)

        with transact:
            rec_count = (self.session_db.query(n6NormalizedData).
                         filter(n6NormalizedData.id == id_event).
                         update({'expires': expires,
                                 'modified': datetime.datetime.utcnow().replace(microsecond=0),
                                 }))
            if rec_count:
                LOGGER.debug("records with the same id %r exist: %r",
                             id_event, rec_count)
            else:
                items = []
                for record in self.records['event']:
                    record["status"] = "active"
                    event = n6NormalizedData(**record)
                    items.append(event)

                for record in self.records['client']:
                    client = n6ClientToEvent(**record)
                    items.append(client)
                LOGGER.debug("bl-update, records with id %r DO NOT EXIST!", id_event)
                LOGGER.debug("insert new events,::count:: %r", len(items))
                self.insert_new_event(items, with_transact=False)

    def suppressed_update(self):
        """
        Agregated event update(change fields: until and count, to the value of  suppressed event).
        """
        LOGGER.debug('* suppressed_update() %r', self.record_dict)

        # add event records from RecordDict
        for event_record in self.record_dict.iter_db_items():
            self.records['event'].append(event_record)

        self.json_to_record(self.records['event'])
        id_event = self.records['event'][0]["id"]
        until = self.records['event'][0]["until"]
        count = self.records['event'][0]["count"]

        # optimization: we can limit time => searching within one partition, not all;
        # it seems that mysql (and/or sqlalchemy?) truncates times to seconds,
        # we are also not 100% sure if other time data micro-distortions are not done
        # -- that's why here we use a 1-second-range instead of an exact value
        first_time_min = parse_iso_datetime_to_utc(
            self.record_dict["_first_time"]).replace(microsecond=0)
        first_time_max = first_time_min + datetime.timedelta(days=0, seconds=1)

        with transact:
            rec_count = (self.session_db.query(n6NormalizedData)
                         .filter(
                             n6NormalizedData.time >= first_time_min,
                             n6NormalizedData.time <= first_time_max,
                             n6NormalizedData.id == id_event)
                         .update({'until': until, 'count': count}))
            if rec_count:
                LOGGER.debug("records with the same id %r exist: %r",
                             id_event, rec_count)
            else:
                items = []
                for record in self.records['event']:
                    event = n6NormalizedData(**record)
                    items.append(event)

                for record in self.records['client']:
                    client = n6ClientToEvent(**record)
                    items.append(client)
                LOGGER.warning("suppressed_update, records with id %r DO NOT EXIST!", id_event)
                LOGGER.debug("insert new events,,::count:: %r", len(items))
                self.insert_new_event(items, with_transact=False)


def main():
    with logging_configured():
        if 'n6integration_test' in os.environ:
            # for debugging only
            LOGGER.setLevel(logging.DEBUG)
            LOGGER.addHandler(logging.StreamHandler(stream=sys.__stdout__))
        d = Recorder()
        try:
            d.run()
        except KeyboardInterrupt:
            d.stop()


if __name__ == "__main__":
    main()

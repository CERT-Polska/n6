# Copyright (c) 2015-2025 NASK. All rights reserved.

import redis
from datetime import datetime
from n6datapipeline.base import LegacyQueuedBase
from n6lib.auth_api import AuthAPI
from n6lib.config import Config
from n6lib.context_helpers import force_exit_on_any_remaining_entered_contexts
from n6lib.db_filtering_abstractions import RecordFacadeForPredicates
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.record_dict import (
    N6DataSpecWithOptionalModified,
    RecordDict,
)


LOGGER = get_logger(__name__)


class Counter(LegacyQueuedBase):

    _VALID_EVENT_TYPES = frozenset([
        'event',
        'bl-new',
        'bl-change',
    ])

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
        'queue_name': 'counter',
        'accepted_event_types': [
            'event',
            'bl-new',
            'bl-change',
        ],
    }

    supports_n6recovery = False

    redis_config_group = "notifier_redis"
    redis_config_required = ("redis_host", "redis_port", "redis_db")
    counter_config_group = "counter"
    counter_config_required = ('max_delta_modified_time',)

    def __init__(self, **kwargs):
        self.redis_config = Config(required={
            self.redis_config_group: self.redis_config_required
        })[self.redis_config_group]
        redis_host = self.redis_config['redis_host']
        redis_port = int(self.redis_config['redis_port'])
        redis_db_number = int(self.redis_config['redis_db'])
        self.pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=redis_db_number, decode_responses=True)
        self.redis_db = redis.StrictRedis(connection_pool=self.pool)
        LOGGER.info('Start redis connection')
        self.redis_pipe = self.redis_db.pipeline()
        self.redis_db.config_set('save', self.redis_config['redis_save'])
        counter_config = Config(required={
            self.counter_config_group: self.counter_config_required
        })[self.counter_config_group]
        self.max_delta_modified_time = int(counter_config['max_delta_modified_time'])
        self.auth_api = AuthAPI()
        self.data_spec = N6DataSpecWithOptionalModified()
        super(Counter, self).__init__(**kwargs)

    def _check_event_type(self, event_type, record_dict):
        if event_type != record_dict.get('type', 'event'):
            raise ValueError(
                "event type from rk ({!a}) does "
                "not match the 'type' item ({!a})"
                .format(event_type, record_dict.get('type')))
        if event_type not in self._VALID_EVENT_TYPES:
            raise ValueError('illegal event type tag: {!a}'.format(event_type))

    def _get_clients_list(self, event_type, record_dict):
        # NOTE: this implementation is similar (but not identical)
        # to n6datapipeline.aux.anonymizer.Anonymizer._get_resource_to_org_ids()
        with self.auth_api:
            subsource_refint = None
            try:
                inside_org_ids = set()
                source = record_dict['source']
                na_info_mapping = (
                    self.auth_api.get_source_ids_to_notification_access_info_mappings()
                    .get(source))
                if na_info_mapping:
                    predicate_ready_dict = RecordFacadeForPredicates(record_dict, self.data_spec)
                    client_org_ids = set(record_dict.get('client', ()))
                    assert all(isinstance(s, str) for s in client_org_ids)
                    for (subsource_refint, _), (predicate, na_org_ids) in na_info_mapping.items():
                        assert all(isinstance(s, str) for s in na_org_ids)
                        na_inside_org_ids = na_org_ids & client_org_ids
                        if not na_inside_org_ids or not predicate(predicate_ready_dict):
                            continue
                        inside_org_ids.update(na_inside_org_ids)
                assert all(isinstance(s, str) for s in inside_org_ids)
                return sorted(inside_org_ids)
            except:
                LOGGER.error(
                    'Could not determine org ids for the "/report/inside" resource '
                    '(event type: %a;  event data: %a%s)',
                    event_type,
                    record_dict,
                    ('' if subsource_refint is None else (
                        ";  lately processed subsource's refint: {!a}"
                        .format(subsource_refint))))
                raise

    def input_callback(self, routing_key, body, properties):
        force_exit_on_any_remaining_entered_contexts(self.auth_api)
        record_dict = RecordDict.from_json(body)
        with self.setting_error_event_info(record_dict):
            modified = record_dict['modified']
            _time = record_dict['time']
            if self.check_diif_time(modified, _time):
                event_type = routing_key.split('.', 1)[0]
                self._check_event_type(event_type, record_dict)
                category = record_dict["category"]
                clients_list = self._get_clients_list(event_type, record_dict)
                for client in clients_list:
                    self.save_to_redis(client, category, modified, _time)

    def save_to_redis(self, cli, category, modified, _time):
        while True:
            try:
                self.redis_pipe.watch(cli)
                self.set_time(cli, _time)
                self.redis_pipe.multi()
                self.redis_pipe.hincrby(cli, category)
                self.redis_pipe.hset(cli, '_tmax', modified)
                self.redis_pipe.hsetnx(cli, '_tmin', modified)  # save if not exist    # <- FIXME? This is OK only if `modified` values are non-decreasing.
                self.redis_pipe.execute()
                break
            except redis.WatchError:
                continue
            finally:
                self.redis_pipe.reset()

    def set_time(self, client, _time):
        time_in_db = self.redis_pipe.hget(client, '_time')
        if (not time_in_db) or self.str_to_datetime(_time) < self.str_to_datetime(time_in_db):
            self.redis_pipe.hset(client, '_time', _time)

    def check_diif_time(self, modified, _time):
        if self.max_delta_modified_time == 0:
            return True
        modified_dt = self.str_to_datetime(modified)
        _time_dt = self.str_to_datetime(_time)
        _time_delta = modified_dt - _time_dt
        _time_delta_days = _time_delta.days
        if _time_delta_days <= self.max_delta_modified_time:
            return True

    def str_to_datetime(self, str_dt):
        str_dt = str_dt.split('.')[0]
        return datetime.strptime(str_dt, "%Y-%m-%d %H:%M:%S")

    def stop(self):
        self.redis_db.save()
        self.pool.disconnect()


def main():
    with logging_configured():
        ct = Counter()
        try:
            ct.run()
        except KeyboardInterrupt:
            ct.stop()
            LOGGER.info('Redis connection closed, exiting...')
            raise


if __name__ == '__main__':
    main()

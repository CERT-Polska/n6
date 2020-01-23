#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
Anonymizer -- performs validation and anonymization of event data
before publishing them using the (STOMP-based) Stream API.
"""

import json

from n6.base.queue import QueuedBase
from n6lib.auth_api import AuthAPI
from n6lib.const import TYPE_ENUMS
from n6lib.context_helpers import force_exit_on_any_remaining_entered_contexts
from n6lib.data_spec import N6DataSpec
from n6lib.db_filtering_abstractions import RecordFacadeForPredicates
from n6lib.log_helpers import get_logger, logging_configured
from n6sdk.pyramid_commons.renderers import data_dict_to_json


LOGGER = get_logger(__name__)


class Anonymizer(QueuedBase):

    # note: here `resource` denotes a *Stream API resource*:
    # "inside" (corresponding to the "inside" access zone) or
    # "threats" (corresponding to the "threats" access zone)
    # -- see the _get_resource_to_org_ids() method below
    OUTPUT_RK_PATTERN = '{resource}.{category}.{anon_source}'

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
        'queue_name': 'anonymizer',
        'binding_keys': [
            '*.filtered.*.*',
        ],
    }

    output_queue = {
        'exchange': 'clients',
        'exchange_type': 'headers',
    }

    basic_prop_kwargs = {'delivery_mode': 1}  # non-persistent

    supports_n6recovery = False

    _VALID_EVENT_TYPES = frozenset(TYPE_ENUMS)

    def __init__(self, **kwargs):
        LOGGER.info("Anonymizer Start")
        super(Anonymizer, self).__init__(**kwargs)
        self.auth_api = AuthAPI()
        self.data_spec = N6DataSpec()

    def input_callback(self, routing_key, body, properties):
        # NOTE: we do not need to use n6lib.record_dict.RecordDict here,
        # because:
        # * previous components (such as filter) have already done the
        #   preliminary validation (using RecordDict's mechanisms);
        # * we are doing the final validation anyway using
        #   N6DataSpec.clean_result_dict() (below -- in the
        #   _get_result_dicts_and_output_body() method)
        event_data = json.loads(body)
        with self.setting_error_event_info(event_data):
            event_type = routing_key.split('.', 1)[0]
            self._process_input(event_type, event_data)

    def _process_input(self, event_type, event_data):
        self._check_event_type(event_type, event_data)
        force_exit_on_any_remaining_entered_contexts(self.auth_api)
        with self.auth_api:
            resource_to_org_ids = self._get_resource_to_org_ids(event_type, event_data)
            if any(org_ids for org_ids in resource_to_org_ids.itervalues()):
                (raw_result_dict,
                 cleaned_result_dict,
                 output_body) = self._get_result_dicts_and_output_body(
                     event_type,
                     event_data,
                     resource_to_org_ids)

                self._publish_output_data(
                    event_type,
                    resource_to_org_ids,
                    raw_result_dict,
                    cleaned_result_dict,
                    output_body)
            else:
                LOGGER.debug('no recipients for event #%s', event_data['id'])

    def _check_event_type(self, event_type, event_data):
        if event_type != event_data.get('type', 'event'):
            raise ValueError(
                "event type from rk ({!r}) does "
                "not match the 'type' item ({!r})"
                .format(event_type, event_data.get('type')))
        if event_type not in self._VALID_EVENT_TYPES:
            raise ValueError('illegal event type tag: {!r}'.format(event_type))

    def _get_resource_to_org_ids(self,
                                 event_type,
                                 event_data):
        subsource_refint = None
        try:
            inside_org_ids = set()
            threats_org_ids = set()
            source = event_data['source']
            subsource_to_saa_info = (
                self.auth_api.get_source_ids_to_subs_to_stream_api_access_infos().get(source))
            if subsource_to_saa_info:
                predicate_ready_dict = RecordFacadeForPredicates(event_data, self.data_spec)
                client_org_ids = set(
                    org_id.decode('ascii', 'strict')
                    for org_id in event_data.get('client', ()))
                for subsource_refint, (
                        predicate, res_to_org_ids) in subsource_to_saa_info.iteritems():
                    subs_inside_org_ids = res_to_org_ids['inside'] & client_org_ids
                    subs_threats_org_ids = res_to_org_ids['threats']
                    if not subs_inside_org_ids and not subs_threats_org_ids:
                        continue
                    if not predicate(predicate_ready_dict):
                        continue
                    inside_org_ids.update(subs_inside_org_ids)
                    threats_org_ids.update(subs_threats_org_ids)
            return {
                'inside': sorted(
                    org_id.decode('ascii', 'strict')
                    for org_id in inside_org_ids),
                'threats': sorted(
                    org_id.decode('ascii', 'strict')
                    for org_id in threats_org_ids),
            }
        except:
            LOGGER.error(
                'Could not determine org ids per resources'
                '(event type: %r;  event data: %r%s)',
                event_type,
                event_data,
                ('' if subsource_refint is None else (
                    ";  lately processed subsource's refint: {!r}".format(subsource_refint))))
            raise

    def _get_result_dicts_and_output_body(self,
                                          event_type,
                                          event_data,
                                          resource_to_org_ids):
        raw_result_dict = cleaned_result_dict = None
        try:
            raw_result_dict = {
                k: v for k, v in event_data.iteritems()
                if (k in self.data_spec.all_result_keys and
                    # eliminating empty `address` and `client` sequences
                    # (as the data spec will not accept them empty):
                    not (k in ('address', 'client') and not v))}
            cleaned_result_dict = self.data_spec.clean_result_dict(
                raw_result_dict,
                auth_api=self.auth_api,
                full_access=False,
                opt_primary=False)
            cleaned_result_dict['type'] = event_type
            # note: the output body will be a cleaned result dict,
            # being an ordinary dict (not a RecordDict instance),
            # with the 'type' item added, serialized to a string
            # using n6sdk.pyramid_commons.renderers.data_dict_to_json()
            output_body = data_dict_to_json(cleaned_result_dict)
            return (
                raw_result_dict,
                cleaned_result_dict,
                output_body,
            )
        except:
            LOGGER.error(
                'Could not prepare an anonymized data record '
                '(event type: %r;  raw result dict: %r;  '
                'cleaned result dict: %r;  %s)',
                event_type,
                raw_result_dict,
                cleaned_result_dict,
                ';  '.join(
                    '`{0}` org ids: {1}'.format(
                        r,
                        ', '.join(map(repr, resource_to_org_ids[r])) or 'none')
                    for r in sorted(resource_to_org_ids)))
            raise

    def _publish_output_data(self,
                             event_type,
                             resource_to_org_ids,
                             raw_result_dict,
                             cleaned_result_dict,
                             output_body):
        done_resource_to_org_ids = {
            resource: []
            for resource in resource_to_org_ids}
        for resource, res_org_ids in sorted(resource_to_org_ids.iteritems()):
            done_org_ids = done_resource_to_org_ids[resource]
            output_rk = self.OUTPUT_RK_PATTERN.format(
                resource=resource,
                category=cleaned_result_dict['category'],
                anon_source=cleaned_result_dict['source'])
            while res_org_ids:
                org_id = res_org_ids[-1]
                try:
                    self.publish_output(
                        routing_key=output_rk,
                        body=output_body,
                        prop_kwargs={'headers': {'n6-client-id': org_id}})
                except:
                    LOGGER.error(
                        'Could not send an anonymized data record, for '
                        'the resource %r, to the client %r (event type: '
                        '%r;  raw result dict: %r;  routing key %r;  '
                        'body: %r;  %s)',
                        resource,
                        org_id,
                        event_type,
                        raw_result_dict,
                        output_rk,
                        output_body,
                        ';  '.join(
                            'for the resource {0!r} -- '
                            '* skipped for the org ids: {1}; '
                            '* done for the org ids: {2}'.format(
                                r,
                                ', '.join(map(repr, resource_to_org_ids[r])) or 'none',
                                ', '.join(map(repr, done_resource_to_org_ids[r])) or 'none')
                            for r in sorted(resource_to_org_ids)))
                    raise
                else:
                    done_org_ids.append(org_id)
                    del res_org_ids[-1]


def main():
    with logging_configured():
        d = Anonymizer()
        try:
            d.run()
        except KeyboardInterrupt:
            d.stop()


if __name__ == "__main__":
    main()

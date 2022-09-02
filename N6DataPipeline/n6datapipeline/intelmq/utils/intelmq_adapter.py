# Copyright (c) 2017-2021 NASK. All rights reserved.

"""
The IntelMQ Adapter component, responsible for communicating
with IntelMQ System.
"""

from logging import getLogger
from typing import Type

import pika

from n6datapipeline.base import LegacyQueuedBase
from n6datapipeline.intelmq.utils.intelmq_converter import (
    IntelToN6Converter,
    N6ToIntelConverter,
)
from n6lib.common_helpers import replace_segment
from n6lib.log_helpers import logging_configured


LOGGER = getLogger(__name__)


class IntelMQAdapter(LegacyQueuedBase):

    """
    IntelMQAdapter provides communication with AMQP
    as a standard N6 component.
    Uses IntelToN6Converter and N6ToIntelConverter
    from utils.intelmq_converter.
    Subclassed by classes providing proper converter
    and routing key.
    """

    converter = NotImplemented
    components_id: str = NotImplemented

    webinput_binding_state: str = 'intelmq-webinput-csv'

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    def set_queue_name(self):
        self.input_queue['queue_name'] = self.components_id

    def get_component_group_and_id(self):
        return 'intelmq-utils', self.components_id

    def get_output_rk(self, input_rk):
        return replace_segment(input_rk, 1, self.components_id)

    def input_callback(self,
                       routing_key: str,
                       body: bytes,
                       properties: pika.BasicProperties) -> None:
        for converted in self.converter(body, routing_key).convert():
            rk = self.get_output_rk(routing_key)
            self.publish_output(routing_key=rk, body=converted)


class N6ToIntel(IntelMQAdapter):

    converter = N6ToIntelConverter
    components_id = 'n6-to-intelmq-adapter'


class IntelToN6(IntelMQAdapter):

    converter = IntelToN6Converter
    components_id = 'intelmq-to-n6-adapter'
    default_event_type = 'event'

    def make_binding_keys(self, binding_states, accepted_event_types):
        # extend the method to generate a specific binding key
        # for the messages sent from the 'intelmq-webinput-csv' tool
        webinput_binding_key = None
        if self.webinput_binding_state in binding_states:
            binding_states.remove(self.webinput_binding_state)
            webinput_binding_key = f'*.{self.webinput_binding_state}'
        super().make_binding_keys(binding_states, accepted_event_types)
        if webinput_binding_key:
            self.input_queue['binding_keys'].append(webinput_binding_key)

    def get_output_rk(self, input_rk):
        parts_input_rk = input_rk.split('.')
        if len(parts_input_rk) < 2:
            rk = f'event.{self.components_id}'
            LOGGER.warning("The input message's routing key (%a) does not consist of at least two "
                           "parts, so the output routing key will be set to: %a", input_rk, rk)
            return f'event.{self.components_id}.{input_rk}'
        if len(parts_input_rk) == 2:
            # If the input message's routing key consists of only
            # two parts, it indicates the message comes from
            # the IntelMQ Webinput CSV component. The output routing
            # key should be prepended with an event type indicator
            # and a component's ID.
            parts_input_rk.insert(0, self.components_id)
            parts_input_rk.insert(0, self.default_event_type)
        else:
            parts_input_rk[1] = self.components_id
        return '.'.join(parts_input_rk)


def _run_adapter(adapter_class: Type[IntelMQAdapter]) -> None:
    with logging_configured():
        adapter_class().run()


def run_intelmq_to_n6():
    _run_adapter(IntelToN6)


def run_n6_to_intelmq():
    _run_adapter(N6ToIntel)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright (c) 2017-2019 NASK
Software Development Department

The IntelMQ Adapter component, responsible for communicating
with IntelMQ System.
"""

from logging import getLogger

from n6.base.queue import QueuedBase
from n6.utils.intelmq.intelmq_converter import (
    IntelToN6Converter,
    N6ToIntelConverter,
)
from n6lib.common_helpers import replace_segment

LOGGER = getLogger(__name__)


class IntelMQAdapter(QueuedBase):
    """
    IntelMQAdapter provides communication with AMQP
    as a standard N6 component.
    Uses IntelToN6Converter and N6ToIntelConverter
    from utils.intelmq_converter.
    Subclassed by classes providing proper converter
    and routing key.
    """

    converter = NotImplemented
    queue_name = NotImplemented
    event_type = 'event'

    input_queue = {
        'exchange': 'integration',
        'exchange_type': 'topic',
        'binding_keys': ['#'],
    }

    output_queue = {
        'exchange': 'integration',
        'exchange_type': 'topic',
    }

    def preinit_hook(self):
        self.input_queue['queue_name'] = self.queue_name
        super(IntelMQAdapter, self).preinit_hook()

    def get_output_rk(self, input_rk):
        return '{}.parsed.{}'.format(self.event_type, input_rk)

    def input_callback(self, routing_key, body, properties):
        for converted in self.converter.convert(body.decode()):
            output_rk = self.get_output_rk(routing_key)
            self.publish_output(routing_key=output_rk, body=converted)


class N6ToIntel(IntelMQAdapter):

    converter = N6ToIntelConverter()
    queue_name = 'n6-to-intelmq'


class IntelToN6(IntelMQAdapter):

    converter = IntelToN6Converter()
    queue_name = 'intelmq-to-n6'


def run_intelmq_to_n6():
    intelmq_to_n6_adapter = IntelToN6()
    intelmq_to_n6_adapter.run()


def run_n6_to_intelmq():
    n6_to_intelmq_adapter = N6ToIntel()
    n6_to_intelmq_adapter.run()

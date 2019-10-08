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

    input_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    output_queue = {
        'exchange': 'event',
        'exchange_type': 'topic',
    }

    def input_callback(self, routing_key, body, properties):
        for converted in self.converter.convert(body.decode()):
            rk = replace_segment(routing_key, 1, self.__class__.__name__.lower())
            self.publish_output(routing_key=rk, body=converted)


class N6ToIntel(IntelMQAdapter):

    converter = N6ToIntelConverter()


class IntelToN6(IntelMQAdapter):

    converter = IntelToN6Converter()


def run_intelmq_to_n6():
    intelmq_to_n6_adapter = IntelToN6()
    intelmq_to_n6_adapter.run()


def run_n6_to_intelmq():
    n6_to_intelmq_adapter = N6ToIntel()
    n6_to_intelmq_adapter.run()

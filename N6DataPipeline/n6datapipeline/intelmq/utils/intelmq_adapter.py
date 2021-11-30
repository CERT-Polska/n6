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

    def input_callback(self,
                       routing_key: str,
                       body: bytes,
                       properties: pika.BasicProperties) -> None:
        for converted in self.converter.convert(body.decode()):
            rk = replace_segment(routing_key, 1, self.components_id)
            self.publish_output(routing_key=rk, body=converted)


class N6ToIntel(IntelMQAdapter):

    converter = N6ToIntelConverter()
    components_id = 'n6-to-intelmq-adapter'


class IntelToN6(IntelMQAdapter):

    converter = IntelToN6Converter()
    components_id = 'intelmq-to-n6-adapter'


def _run_adapter(adapter_class: Type[IntelMQAdapter]) -> None:
    with logging_configured():
        adapter_class().run()


def run_intelmq_to_n6():
    _run_adapter(IntelToN6)


def run_n6_to_intelmq():
    _run_adapter(N6ToIntel)

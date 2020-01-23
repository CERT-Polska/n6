# -*- coding: utf-8 -*-

# Copyright (c) 2013-2019 NASK. All rights reserved.

"""
Collectors: packetmail-net.list, packetmail-net.ratware-list,
packetmail-net.others-list
"""

import sys

from n6.collectors.generic import (
    BaseOneShotCollector,
    BaseUrlDownloaderCollector,
    entry_point_factory,
)
from n6lib.log_helpers import get_logger

LOGGER = get_logger(__name__)


class _PacketmailBaseCollector(BaseUrlDownloaderCollector, BaseOneShotCollector):

    type = 'file'
    content_type = 'text/text'

    def process_data(self, data):
        return data


class PacketmailScanningCollector(_PacketmailBaseCollector):

    config_group = 'packetmail_net_scanning'

    def get_source_channel(self, **kwargs):
        return 'list'


class PacketmailRatwareCollector(_PacketmailBaseCollector):

    config_group = 'packetmail_net_ratware'

    def get_source_channel(self, **kwargs):
        return 'ratware-list'


class PacketmailOthersCollector(_PacketmailBaseCollector):

    config_group = 'packetmail_net_others'

    def get_source_channel(self, **kwargs):
        return 'others-list'


entry_point_factory(sys.modules[__name__])

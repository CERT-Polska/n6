# Copyright (c) 2024 NASK. All rights reserved.

"""
Parser: `withaname.ddosia`.
"""

import csv
import json
from collections.abc import Generator
from io import StringIO
from typing import Any

from n6datasources.parsers.base import (
    BaseParser,
    add_parser_entry_point_functions
)
from n6lib.log_helpers import get_logger
from n6lib.record_dict import RecordDict, AdjusterError

LOGGER = get_logger(__name__)

PROTOCOLS_TYPES = frozenset(["http", "http2", "http3", "nginx_loris", "tcp"])


class WithanameDdosiaParser(BaseParser):
    default_binding_key = "withaname.ddosia"

    constant_items = {
        "restriction": "need-to-know",
        "confidence": "low",
        "category": "dos-victim",
    }

    def parse(self, data: dict) -> Generator[RecordDict, Any, None]:
        event = json.loads(data["raw"])
        csv_file: str = event['csv_file']
        datetime = event['datetime']

        reader = csv.DictReader(StringIO(csv_file))

        for row in reader:
            with self.new_record_dict(data) as parsed:
                parsed["address"] = {"ip": row["ip"]}
                parsed["time"] = datetime
                parsed["fqdn"] = row["host"]

                dport = row['port']
                try:
                    parsed['dport'] = dport
                except AdjusterError:
                    LOGGER.warning('invalid value of dport: %s', dport)

                if row["method"] == "PING":
                    parsed["proto"] = "icmp"
                elif row["type"] == "udp":
                    parsed["proto"] = "udp"
                elif row["type"] in PROTOCOLS_TYPES:
                    parsed["proto"] = "tcp"

                parsed["name"] = f"DDoSia victim ({row['type']} {row['method']})"

                yield parsed


add_parser_entry_point_functions(__name__)

# Copyright (c) 2024 NASK. All rights reserved.

"""
Collector: `withaname.ddosia`.
"""

from __future__ import annotations

import json
import re
from collections.abc import (
    Generator,
    Iterator,
)
from datetime import datetime

from n6datasources.collectors.base import (
    BaseDownloadingCollector,
    BaseTwoPhaseCollector,
    StatefulCollectorMixin,
    add_collector_entry_point_functions,
)
from n6lib.config import combined_config_spec
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)


class WithanameDdosiaCollector(StatefulCollectorMixin,
                               BaseTwoPhaseCollector,
                               BaseDownloadingCollector,
                               ):
    DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
    CSV_LINK_NAME_PATTERN = re.compile(r'href="((?!last\.csv)[^"]+\.csv)"')
    CSV_HEADER_PATTERN = "host,ip,type,method,port,use_ssl,path\r\n"

    content_type = "text/csv"
    raw_type = "file"

    config_spec_pattern = combined_config_spec("""
        [{collector_class_name}]
        url :: str
        download_retries = 3 :: int
    """)

    def get_source(self, **processed_data: KwargsDict) -> str:
        return "withaname.ddosia"

    def make_default_state(self) -> datetime:
        return datetime(1970, 1, 1, 00, 00, 00)

    def obtain_input_pile(self) -> Generator[KwargsDict] | None:
        self._state = self.load_state()
        raw_html_data = self._fetch_raw_data()
        csv_links = self._retrieve_and_sort_csv_links(raw_html_data)
        yield from self._fetch_and_process_csv_files(csv_links)

    def _fetch_raw_data(self) -> str:
        return self.download_text(url=self.config["url"])

    def get_output_data_body(
            self,
            *,
            data_body: Generator[KwargsDict],
            **processed_data: KwargsDict,
    ) -> bytes:
        return bytes(json.dumps(data_body), 'utf-8')

    def generate_input_data_dicts(
            self,
            input_pile: Generator[KwargsDict]
    ) -> Iterator[KwargsDict]:
        for data_body in input_pile:
            yield {"data_body": data_body}

    def _fetch_and_process_csv_files(
            self,
            csv_links: list[tuple[str, datetime]],
    ) -> Generator[KwargsDict]:
        if not csv_links:
            LOGGER.info("No CSV links found.")
            return

        base_url = self.config["url"]

        for link, date in csv_links:
            csv_file = self._fetch_csv_file(base_url, link)
            if csv_file == self.CSV_HEADER_PATTERN or not csv_file:
                LOGGER.info("the csv file contains no data.")
                continue

            yield {'csv_file': csv_file, 'datetime': date}

    def _fetch_csv_file(self, base_url: str, path_url: str = "") -> str:
        return self.download(base_url + path_url).decode()

    def _retrieve_and_sort_csv_links(self, data: str) -> list[tuple[str, datetime]]:
        csv_links = [
            (link, self._extract_date_from_link(link))
            for link in self.CSV_LINK_NAME_PATTERN.findall(data)
            if self._extract_date_from_link(link) is not None
               and self._extract_date_from_link(link) > self._state
        ]

        if not csv_links:
            LOGGER.info("No new data.")
            return []

        csv_links.sort(key=lambda x: x[1])
        self._state = csv_links[-1][1]

        return [(link, date.isoformat()) for link, date in csv_links]

    def _extract_date_from_link(self, link_name: str) -> datetime | None:
        match = self.DATE_PATTERN.search(link_name)
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d_%H-%M-%S")
        except ValueError as e:
            LOGGER.error(f"Error parsing date from link {link_name}: {e}")
            return None

    def after_completed_publishing(self) -> None:
        super().after_completed_publishing()
        self.save_state(self._state)

add_collector_entry_point_functions(__name__)

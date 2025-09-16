# Copyright (c) 2013-2023 NASK. All rights reserved.

import datetime
import json
import os
import pickle
import sys
import tempfile
import unittest
from collections import namedtuple
from functools import cached_property
from pathlib import Path
from unittest.mock import (
    MagicMock,
    call,
    patch,
    sentinel,
)

from pika.exceptions import AMQPError
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datapipeline.base import (
    n6AMQPCommunicationError,
    n6QueueProcessingException,
)
from n6datapipeline.aggregator import (
    Aggregator,
    AggregatorData,
    AggregatorDataManager,
    PayloadStorage,
    HiFreqEventData,
    SourceData,
)
from n6lib.config import ConfigSection
from n6lib.file_helpers import FileAccessor
from n6lib.unit_test_helpers import TestCaseMixin


_tmp_dir = tempfile.TemporaryDirectory(prefix=__name__)


@expand
class TestAggregator(TestCaseMixin, unittest.TestCase):

    sample_dbpath = f"{_tmp_dir.name}/sample_dbfile"
    sample_time_tolerance = 600
    sample_time_tolerance_per_source = {
        'anotherprovider.andchannel': 1200,
    }

    starting_datetime = datetime.datetime(2017, 6, 1, 10)
    mocked_utcnow = datetime.datetime(2017, 7, 1, 7, 0, 0)

    input_callback_proper_msg = (
        b'{'
        b'"source": "testprovider.testchannel",'
        b'"_group": "group1",'
        b'"id": "d41d8cd98f00b204e9800998ecf8427b",'
        b'"time": "2017-06-01 10:00:00"'
        b'}'
    )
    input_callback_msg_no__group = (
        b'{'
        b'"source": "testprovider.testchannel",'
        b'"id": "d41d8cd98f00b204e9800998ecf8427b",'
        b'"time": "2017-06-01 10:00:00"'
        b'}'
    )

    mocked_config = {
        "aggregator": {
            "dbpath": sample_dbpath,
            "time_tolerance": str(sample_time_tolerance),
            "time_tolerance_per_source": repr(sample_time_tolerance_per_source),
        }
    }
    resultant_config = ConfigSection("aggregator", {
        "dbpath": sample_dbpath,
        "time_tolerance": sample_time_tolerance,
        "time_tolerance_per_source": sample_time_tolerance_per_source,  # (<- *non*-default value)
        'finished_groups_count_triggering_restart': 10_000_000,  # (<- default value)
    })


    @paramseq
    def _expected_exc_from_super_run():
        for c in [KeyboardInterrupt, AMQPError, n6AMQPCommunicationError]:  # (expected excs)
            yield c()
            yield c('blabla')
            try:
                raise SystemExit from c
            except SystemExit as exc:
                yield exc
            try:
                raise SystemExit(1) from c('blabla')
            except SystemExit as exc:
                yield exc
            try:
                try:
                    raise c()
                except c:
                    sys.exit(1)
            except SystemExit as exc:
                yield exc
                try:
                    raise SystemExit(1) from exc
                except SystemExit as e:
                    yield e
                try:
                    raise SystemExit(1)
                except SystemExit as e:
                    yield e

    @paramseq
    def _unexpected_exc_from_super_run():
        for c in [SystemExit, ValueError, n6QueueProcessingException]:  # (arbitrary example excs)
            yield c()
            yield c('blabla')
            try:
                raise SystemExit from c
            except SystemExit as exc:
                yield exc
            try:
                raise SystemExit(1) from c('blabla')
            except SystemExit as exc:
                yield exc
            try:
                try:
                    raise c()
                except c:
                    sys.exit(1)
            except SystemExit as exc:
                yield exc
                try:
                    raise SystemExit(1) from exc
                except SystemExit as e:
                    yield e
                try:
                    raise SystemExit(1)
                except SystemExit as e:
                    yield e
        yield SystemExit(1)
        for c2 in [KeyboardInterrupt, AMQPError, n6AMQPCommunicationError]:
            try:
                try:
                    raise c2()
                except c2:
                    raise SystemExit(1) from None
            except SystemExit as exc:
                yield exc


    @paramseq
    def _ordered_data_to_process(cls):
        # Three events are published, each one of a different group.
        yield param(
            input_data=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "c81e728d9d4c2f636f067f89cc14862c",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "eccbc87e4b5ce2fe28308fd9f2a7baf3",
                    "source": "testprovider.testchannel",
                    "_group": "group3",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=1)),
                },
            ],
            expected_ids_to_single_events=[
                "c4ca4238a0b923820dcc509a6f75849b",
                "c81e728d9d4c2f636f067f89cc14862c",
                "eccbc87e4b5ce2fe28308fd9f2a7baf3"
            ],
        )

        # First events of three groups are published; events
        # of "group1" and "group2" are aggregated. The last
        # event is published and it triggers publishing of
        # aggregated events - its time difference exceeds
        # the `AGGREGATE_WAIT` parameter.
        yield param(
            input_data=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "c81e728d9d4c2f636f067f89cc14862c",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426f",
                    "source": "testprovider.testchannel",
                    "_group": "group3",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427a",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=1)),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=1)),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=2)),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=14)),
                },
            ],
            expected_ids_to_single_events=[
                "c4ca4238a0b923820dcc509a6f75849b",
                "c81e728d9d4c2f636f067f89cc14862c",
                "d41d8cd98f00b204e9800998ecf8426f",
                "d41d8cd98f00b204e9800998ecf8427d"
            ],
            expected_ids_to_suppressed_events={
                "c4ca4238a0b923820dcc509a6f75849b": {
                    '_first_time': str(cls.starting_datetime),
                    # the 'until' value is the time of the
                    # excluding the event that triggered
                    # publishing of aggregated events
                    "until": str(cls.starting_datetime + datetime.timedelta(hours=2)),
                    # the event that triggered publishing
                    # of aggregated events is not included
                    # in the count, it will be published
                    # with next group of aggregated events
                    "count": 3,
                },
                "c81e728d9d4c2f636f067f89cc14862c": {
                    "_first_time": str(cls.starting_datetime),
                    "until": str(cls.starting_datetime + datetime.timedelta(hours=1)),
                    "count": 2,
                },
            },
        )

        # The latest event is 12 hours older than the last event
        # of 'group2', but not than the last event of 'group1'.
        # Suppressed events are published only for the 'group2'.
        # There is only one event from the 'group3', so no suppressed
        # events are published for it.
        yield param(
            input_data=[
                {
                    "id": "11111111111111111111111111111111",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "22222222222222222222222222222222",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": "2017-06-01 08:02:00",
                },
                {
                    "id": "33333333333333333333333333333333",
                    "source": "testprovider.testchannel",
                    "_group": "group3",
                    "time": "2017-06-01 08:04:00",
                },
                {
                    "id": "44444444444444444444444444444444",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "55555555555555555555555555555555",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": "2017-06-01 09:00:20",
                },
                {
                    "id": "66666666666666666666666666666666",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "77777777777777777777777777777777",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 21:30:00",
                },
            ],
            expected_ids_to_single_events=[
                "11111111111111111111111111111111",
                "22222222222222222222222222222222",
                "33333333333333333333333333333333",
            ],
            expected_ids_to_suppressed_events={
                "22222222222222222222222222222222": {
                    "until": "2017-06-01 09:00:20",
                    "_first_time": "2017-06-01 08:02:00",
                    "count": 2,
                }
            }
        )

        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 01:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:01',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 12:00:01',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
            ],
        ).label('The first event is published as "event", next two are aggregated.')

        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 01:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 02:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 14:00:01',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
            expected_ids_to_suppressed_events={
                "d41d8cd98f00b204e9800998ecf8427b": {
                    "until": "2017-06-01 02:00:00",
                    "_first_time": "2017-06-01 01:00:00",
                    "count": 2,
                },
            },
        ).label("Last event is 12 hours older than the previous one, it triggers publishing "
                "of suppressed events.")

        # The latest 'group1' event is from the next day, so
        # it triggers publishing of suppressed events for the 'group1'.
        # There is only one 'group2' event, so there is no suppressed
        # event for it.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 18:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 20:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-02 01:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "d41d8cd98f00b204e9800998ecf8427c",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
            expected_ids_to_suppressed_events={
                "d41d8cd98f00b204e9800998ecf8427b": {
                    "until": "2017-06-01 20:00:00",
                    "_first_time": "2017-06-01 18:00:00",
                    "count": 2,
                }
            }
        )

        # The 'group2' latest event is from the next day, comparing
        # to previous events, so it triggers publishing of suppressed
        # events from the 'group1' and 'group2'.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 18:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8425c",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:28:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 20:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-02 01:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "d41d8cd98f00b204e9800998ecf8427c",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
            expected_ids_to_suppressed_events={
                "d41d8cd98f00b204e9800998ecf8427b": {
                    "until": "2017-06-01 20:00:00",
                    "_first_time": "2017-06-01 18:00:00",
                    "count": 2,
                },
                "d41d8cd98f00b204e9800998ecf8427c": {
                    "until": "2017-06-01 19:28:00",
                    "_first_time": "2017-06-01 19:00:00",
                    "count": 2,
                },
            }
        )

        # The third event is older than the current time, but it is
        # newer than the first event from its group, so it is still
        # aggregated. The last event triggers publishing of suppressed
        # events.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 12:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 11:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-02 11:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
            expected_ids_to_suppressed_events={
                "d41d8cd98f00b204e9800998ecf8427b": {
                    "count": 3,
                    "_first_time": "2017-06-01 10:00:00",
                    "until": "2017-06-01 12:00:00",
                },
            },
            expected_last_active_dt_updates=3,
        )

        # The second event is older than the current time, but it is
        # within the time tolerance, so it is still aggregated.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:51:00",  # time within mocked time tolerance
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-02 11:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
            expected_ids_to_suppressed_events={
                "d41d8cd98f00b204e9800998ecf8427b": {
                    "count": 2,
                    "until": "2017-06-01 10:00:00",
                    "_first_time": "2017-06-01 10:00:00",
                },
            },
        )

        # The second and fourth event is older than the current time,
        # but fits the time tolerance for specific source, so it is
        # still aggregated.
        yield param(
            input_data=[
                {
                    "id": "11111111111111111111111111111111",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "22222222222222222222222222222222",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:51:00",  # within time tolerance
                },
                {
                    "id": "33333333333333333333333333333333",
                    "source": "anotherprovider.andchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:00',
                },
                {
                    "id": "44444444444444444444444444444444",
                    "source": "anotherprovider.andchannel",
                    "_group": "group1",
                    "time": '2017-06-01 10:40:00',   # within time tolerance
                },
            ],
            expected_ids_to_single_events=[
                "11111111111111111111111111111111",
                "33333333333333333333333333333333",
            ],
        )

        # The newest event, which triggers publishing of suppressed
        # events, has next day's date, but it also has to be
        # greater than the time of a checked group's last
        # event by more than the `time_tolerance`. Otherwise,
        # further publishing of suppressed events is stopped.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 17:00:00",
                },
                {
                    "id": "53b325261706c63aed655a3ca8810780",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 18:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427f",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 23:57:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-02 00:03:01',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "53b325261706c63aed655a3ca8810780",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
        )

        # The newest event has a time greater than the last
        # "group1" event by more than the `time_tolerance`,
        # so suppressed events are published for the group.
        # Then, after checking "group2", the event does not
        # meet this condition, so publishing of suppressed
        # events is stopped here. No suppressed events
        # are published for the "group2".
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 17:00:00",
                },
                {
                    "id": "53b325261706c63aed655a3ca8810780",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 18:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427f",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 23:57:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-02 00:03:01',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
                "53b325261706c63aed655a3ca8810780",
                "d41d8cd98f00b204e9800998ecf8427e",
            ],
            expected_ids_to_suppressed_events={
                "d41d8cd98f00b204e9800998ecf8427b": {
                    "_first_time": "2017-06-01 17:00:00",
                    "until": "2017-06-01 19:00:00",
                    "count": 2,
                },
            },
        )

    @paramseq
    def _unordered_data_to_process(cls):
        # The first event is published, second and third are ignored,
        # because they are older than the current time (event with
        # the time tolerance added) and older than the first event
        # of the group. Last event is aggregated.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
            ],
            # Number of times the `SourceData` instance's `last_active`
            # datetime is expected to be updated. It should not be
            # updated, if the event is out of order.
            expected_last_active_dt_updates=2,
        )

        # The first event is published. The second is ignored,
        # because it is older than the current time, and its group
        # has not been registered before. The third one is older
        # than the current time, and older than the first event
        # of its group. The last one is aggregated.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426d",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
            ],
            expected_last_active_dt_updates=2,
        )

    @paramseq
    def _unordered_data_to_process_event__buffer_may_contain_suppressed_event_1(cls):
        # The first, second, and third event are published. The last event is unique.
        # The first has a new group. The second with the same group achieved aggregated time.
        # The third event has a new group. The last event is older than the time of the source,
        # but it fits in the tolerance range. There is not a high-frequency event of 'group1'
        # in the groups dict, but it still remains in the buffer. Because of it, the event is
        # neither being published nor aggregated, but the count attribute of related high-frequency
        # event in the buffer is incremented.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998bcdef351",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 00:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef352",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 23:51:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef353",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": "2020-01-02 00:01:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef354",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-02 00:00:00",
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998bcdef351",
                "d41d8cd98f00b204e9800998bcdef352",
                "d41d8cd98f00b204e9800998bcdef353",
            ],
            expected_last_active_dt_updates=3,
        )

    @paramseq
    def _unordered_data_to_process_event__buffer_may_contain_suppressed_event_2(cls):
        # The first and third event are published. The second is aggregated. The last event is
        # unique. The first has a new group. The second with the same group fits in the aggregated
        # range time. The third event has a new group so published.
        # The last event is older than the time of the source, but it fits in the tolerance range.
        # There is not a high-frequency event of 'group1' in the groups dict, but it still remains
        # in the buffer. Because of it, the event is neither being published nor aggregated,
        # but the count attribute of related high-frequency event in the buffer is incremented.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998bcdef351",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 22:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef352",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 23:51:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef353",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": "2020-01-02 00:01:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef354",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-02 00:00:00",
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998bcdef351",
                "d41d8cd98f00b204e9800998bcdef353",
            ],
            expected_last_active_dt_updates=3,
        )

    @paramseq
    def _unordered_data_to_process_event__buffer_may_contain_suppressed_event_3(cls):
        # All events are published. The first has a new group. The second with the same group
        # achieved aggregated time. The third event has a new group so published.
        # The last event has a new group and is older than the time of the source, but it fits
        # in the tolerance range. The difference between the case and other two similar
        # cases is that it does not fulfill the condition, that a 'group1' hi-freq
        # event still remains in the buffer - the buffer has been cleared, because
        # the difference between the source time and 'until' time of the last event
        # of 'group1' exceeds the tolerance range. So instead of suppressing the
        # last 'group1' event and incrementing the hi-freq event's counter,
        # the new event is being published.

        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998bcdef351",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 00:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef352",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 20:51:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef353",
                    "source": "testprovider.testchannel",
                    "_group": "group2",
                    "time": "2020-01-02 22:01:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998bcdef354",
                    "source": "testprovider.testchannel",
                    "_group": "group1",
                    "time": "2020-01-02 22:00:00",
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998bcdef351",
                "d41d8cd98f00b204e9800998bcdef352",
                "d41d8cd98f00b204e9800998bcdef353",
                "d41d8cd98f00b204e9800998bcdef354",
            ],
            expected_last_active_dt_updates=4,
        )


    def setUp(self):
        self._payload_storage = PayloadStorage._make_for_tests()
        self.addCleanup(self._payload_storage.close)
        self._published_events = []
        self._aggregator = Aggregator.__new__(Aggregator)
        aggr_data_manager = AggregatorDataManager.__new__(AggregatorDataManager)
        aggr_data_manager.aggr_data = AggregatorData()
        aggr_data_manager.time_tolerance = datetime.timedelta(seconds=self.sample_time_tolerance)
        aggr_data_manager.time_tolerance_per_source = {
            source: datetime.timedelta(seconds=time_tolerance)
            for source, time_tolerance in self.sample_time_tolerance_per_source.items()}
        self._mocked_datetime_counter = 0
        self._aggregator.db = aggr_data_manager
        self._aggregator._finished_groups_count = 0


    def test_run__with_no_exc(self):
        m = MagicMock()
        aggregator = self._aggregator
        aggregator.db.store_state = m.store_state
        self.patch('n6datapipeline.base.LegacyQueuedBase.run', m.super_run)
        self.patch('n6datapipeline.base.LegacyQueuedBase.stop', m.super_stop)

        aggregator.run()

        self.assertEqual(m.mock_calls, [
            call.super_run(),
            call.store_state(),
        ])


    @foreach(_expected_exc_from_super_run)
    @foreach([True, False])  # <- Shall *raise exception from `stop()`*?
    def test_run__with_expected_exc_from_super_run(self, raise_exception_from_stop, exc):
        assert isinstance(raise_exception_from_stop, bool)
        m = MagicMock()
        m.super_run.side_effect = exc
        if raise_exception_from_stop:
            m.super_stop.side_effect = Exception('<whatever>')
            m.super_stop.__qualname__ = '<name irrelevant here>'
        aggregator = self._aggregator
        aggregator.db.store_state = m.store_state
        self.patch('n6datapipeline.base.LegacyQueuedBase.run', m.super_run)
        self.patch('n6datapipeline.base.LegacyQueuedBase.stop', m.super_stop)

        with self.assertRaises(type(exc)):
            aggregator.run()

        self.assertEqual(m.mock_calls, [
            call.super_run(),
            # Before propagating `exc`, first stored the state...
            call.store_state(),
            # ...and attempted to stop the IO loop (suppressing
            # an `Exception`-derived error from `stop()`, if any)
            call.super_stop(),
        ])


    @foreach(_unexpected_exc_from_super_run)
    def test_run__with_unexpected_exc_from_super_run(self, exc):
        m = MagicMock()
        m.super_run.side_effect = exc
        aggregator = self._aggregator
        aggregator.db.store_state = m.store_state
        self.patch('n6datapipeline.base.LegacyQueuedBase.run', m.super_run)
        self.patch('n6datapipeline.base.LegacyQueuedBase.stop', m.super_stop)

        with self.assertRaises(type(exc)):
            aggregator.run()

        self.assertEqual(m.mock_calls, [
            call.super_run(),
            # Just propagated `exc`, *without* storing the state.
        ])


    @foreach(_ordered_data_to_process
             + _unordered_data_to_process_event__buffer_may_contain_suppressed_event_1
             + _unordered_data_to_process_event__buffer_may_contain_suppressed_event_2
             + _unordered_data_to_process_event__buffer_may_contain_suppressed_event_3)
    def test_processing_events(self,
                               input_data,
                               expected_ids_to_single_events=None,
                               expected_ids_to_suppressed_events=None,
                               expected_last_active_dt_updates=None):

        if expected_last_active_dt_updates is None:
            expected_last_active_dt_updates = len(input_data)

        self._test_process_event(input_data,
                                 expected_ids_to_single_events,
                                 expected_ids_to_suppressed_events,
                                 expected_last_active_dt_updates)


    @foreach(_unordered_data_to_process)
    def test_processing_unordered_events(self,
                                         input_data,
                                         expected_ids_to_single_events=None,
                                         expected_ids_to_suppressed_events=None,
                                         expected_last_active_dt_updates=None):

        if expected_last_active_dt_updates is None:
            expected_last_active_dt_updates = len(input_data)

        with self.assertRaisesRegex(n6QueueProcessingException, r"\bEvent out of order\b"):
            self._test_process_event(input_data,
                                     expected_ids_to_single_events,
                                     expected_ids_to_suppressed_events,
                                     expected_last_active_dt_updates)


    @foreach([
        param(
            count=123,
            expected_body_content={
                "source": "ham.spam",
                "type": "foobar",
                "count": 123,
            },
        ).label("quite small count"),
        param(
            count=32768,
            expected_body_content={
                "source": "ham.spam",
                "type": "foobar",
                "count": 32768,
            },
        ).label("count over the old limit"),  # (old limit was `32767`)
        param(
            count=2 ** 32 - 1,
            expected_body_content={
                "source": "ham.spam",
                "type": "foobar",
                "count": 2 ** 32 - 1,
            },
        ).label("maximum count (unrealistically big...)"),
    ])
    def test_publish_event(self, count, expected_body_content):
        event_type = "foobar"
        payload = {
            "source": "ham.spam",
            "_group": "something",
            "count": count,
        }
        data = event_type, payload
        expected_routing_key = "foobar.aggregated.ham.spam"
        self._aggregator.publish_output = MagicMock()

        self._aggregator.publish_event(data)

        self.assertEqual(len(self._aggregator.publish_output.mock_calls), 1)
        publish_output_kwargs = self._aggregator.publish_output.mock_calls[0][-1]
        self.assertEqual(set(publish_output_kwargs.keys()), {"routing_key", "body"})
        self.assertEqual(publish_output_kwargs["routing_key"], expected_routing_key)
        self.assertJsonEqual(publish_output_kwargs["body"], expected_body_content)


    @foreach([
        param(
            finished_groups_count=0,
            expected_graceful_shutdown_method_calls=[],
        ),
        param(
            finished_groups_count=41,
            expected_graceful_shutdown_method_calls=[],
        ),
        param(
            finished_groups_count=42,
            expected_graceful_shutdown_method_calls=[call()],
        ),
    ])
    def test_input_callback(self, finished_groups_count, expected_graceful_shutdown_method_calls):
        expected_process_event_calls = [call(json.loads(self.input_callback_proper_msg))]
        self._aggregator.process_event = process_event_mock = MagicMock()
        self._aggregator.trigger_inner_stop_trying_gracefully_shutting_input_then_output = \
            graceful_shutdown_method_mock = MagicMock()
        self._aggregator.config = ConfigSection("<name irrelevant here>", {
            "finished_groups_count_triggering_restart": 42,
        })
        self._aggregator._finished_groups_count = finished_groups_count

        self._aggregator.input_callback("testprovider.testchannel",
                                        self.input_callback_proper_msg,
                                        sentinel.Properties)

        self.assertEqual(
            process_event_mock.mock_calls,
            expected_process_event_calls,
        )
        self.assertEqual(
            graceful_shutdown_method_mock.mock_calls,
            expected_graceful_shutdown_method_calls,
        )


    def test_input_callback_with__group_missing(self):
        with self.assertRaisesRegex(n6QueueProcessingException, r"\bmissing '_group' field\b"):
            with patch.object(Aggregator, "process_event"):
                self._aggregator.input_callback("testprovider.testchannel",
                                                self.input_callback_msg_no__group,
                                                sentinel.Properties)


    @patch("n6datapipeline.base.LegacyQueuedBase.__init__", autospec=True)
    @patch("n6datapipeline.aggregator.AggregatorDataManager", return_value=sentinel.db)
    @patch("n6lib.config.Config._load_n6_config_files", return_value=mocked_config)
    def test_init(self, config_mock, db_constructor_mock, super__init__mock):
        fp = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as fp:
                pickle.dump('whatever', fp)
            expected_config = self.resultant_config.copy()
            config_mock.return_value["aggregator"]["dbpath"] = expected_config["dbpath"] = fp.name

            self._aggregator.__init__()

            self.assertEqual(super__init__mock.mock_calls, [
                call(self._aggregator),
            ])

            self.assertTrue(hasattr(self._aggregator, "config"))
            self.assertIsInstance(self._aggregator.config, ConfigSection)
            self.assertEqual(self._aggregator.config, expected_config)

            self.assertTrue(hasattr(self._aggregator, "db"))
            self.assertIs(self._aggregator.db, sentinel.db)
            self.assertEqual(db_constructor_mock.mock_calls, [
                call(
                    expected_config["dbpath"],
                    time_tolerance=datetime.timedelta(seconds=expected_config["time_tolerance"]),
                    time_tolerance_per_source={
                        source: datetime.timedelta(seconds=seconds)
                        for source, seconds in expected_config["time_tolerance_per_source"].items()
                    },
                ),
            ])
        finally:
            if fp is not None:
                os.remove(fp.name)

        # state directory does not exist
        with tempfile.NamedTemporaryFile() as fp, \
                self.assertRaisesRegex(Exception, r"state directory does not exist"):
            config_mock.return_value["aggregator"]["dbpath"] = os.path.join(fp.name,
                                                                            "nonexistent_file")
            self._aggregator.__init__()

        # state directory exists, but we have no write access to it
        with tempfile.NamedTemporaryFile() as fp, \
                patch("os.access", return_value=None), \
                self.assertRaisesRegex(Exception, r"write access to the state directory needed"):
            config_mock.return_value["aggregator"]["dbpath"] = fp.name
            self._aggregator.__init__()


    def _mocked_utcnow_method(self):
        """
        Helper method used as a side effect of a mocked
        datetime.datetime.utcnow() method. Increment the counter
        during each call, which will indicate how many times
        utcnow() was called.
        """
        self._mocked_datetime_counter += 1
        return self.mocked_utcnow


    def _test_process_event(self,
                            input_data,
                            expected_ids_to_single_events,
                            expected_ids_to_suppressed_events,
                            expected_last_active_dt_updates):
        """
        Use input data to call Aggregator's `process_event()` method;
        use it to create expected events and compare it with events
        crated based on arguments that QueuedBase's `publish_output()`
        method was called with (`publish_output()` normally, if not
        mocked, would publish actual events created from
        this arguments).
        """
        expected_events = []

        with patch("n6datapipeline.aggregator.datetime") as datetime_mock,\
                patch.object(Aggregator, "publish_output") as publish_output_mock:
            datetime_mock.datetime.utcnow.side_effect = self._mocked_utcnow_method
            datetime_mock.datetime.side_effect = (lambda *args, **kw:
                                                  datetime.datetime(*args, **kw))
            # a `SourceData` attribute `time_tolerance` needs
            # a `datetime.timedelta` instance, but it is mocked now
            datetime_mock.timedelta.side_effect = (lambda *args, **kw:
                                                   datetime.timedelta(*args, **kw))
            for event in input_data:
                if expected_ids_to_single_events and event["id"] in expected_ids_to_single_events:
                    expected_events.append(
                        self._get_expected_event_from_input_data(event.copy(), "event"))
                if (expected_ids_to_suppressed_events
                        and event["id"] in expected_ids_to_suppressed_events):
                    new_suppressed = event.copy()
                    new_suppressed.update(expected_ids_to_suppressed_events[event["id"]])
                    expected_events.append(
                        self._get_expected_event_from_input_data(new_suppressed, "suppressed"))
                self._aggregator.process_event(event)
        events_from_calls = self._get_events_from_calls(publish_output_mock.call_args_list)
        self.assertCountEqual(expected_events, events_from_calls)
        # Check how many times datetime.datetime.utcnow() was called,
        # meaning how many times the `SourceData` instance's
        # `last_active` attribute was updated. It should not be updated
        # when the event is out of order (we assume the source was not
        # active if it published an old event).
        self.assertEqual(self._mocked_datetime_counter, expected_last_active_dt_updates)


    @staticmethod
    def _get_expected_event_from_input_data(input_data, event_type):
        """
        Turn an input data to event-like dicts, that are expected
        to be created during the calls to `process_event()` method.
        Args:
            `input_data`:
                a dict with input data.
            `event_type`:
                a type of event ('event' or 'suppressed').

        Returns:
            an event-like dict, that is expected to be created
            during the call to `process_event()`.
        """
        input_data.update({"type": event_type})
        # final events do not contain field `_group`
        del input_data["_group"]
        return {
            "body": input_data,
            "routing_key": f"{event_type}.aggregated.{input_data['source']}",
        }


    @staticmethod
    def _get_events_from_calls(call_args_list):
        """
        Turn a list of calls to method to actual event-like
        dicts, which would be created during a regular Aggregator
        run.
        """
        events_from_calls = []
        for _, call_args in call_args_list:
            events_from_calls.append({"body": json.loads(call_args["body"]),
                                      "routing_key": call_args["routing_key"]})
        return events_from_calls


@expand
class TestAggregatorDataManager(unittest.TestCase):

    tested_source = "testprovider.testchannel"
    other_source = "otherprovider.otherchannel"
    sample_aggr_data_path = Path(_tmp_dir.name, "example.pickle")
    sample_time_tolerance = 600
    sample_time_tolerance_per_source = {
        other_source: 1200,
    }
    mocked_utcnow = datetime.datetime(2017, 7, 1, 12, 0, 0)
    sources_tested_for_inactivity = [tested_source, other_source]

    group1_expected_suppressed_payload = dict(
        count=5,
        _first_time="2017-06-01 07:00:00",
        id="c4ca4238a0b923820dcc509a6f75849b",
        source=tested_source,
        time="2017-06-01 07:00:00",
        _group="group1",
        until="2017-06-01 09:00:00",
    )
    group1_expected_suppressed_event = (
        "suppressed",
        group1_expected_suppressed_payload,
    )
    group2_expected_suppressed_payload = dict(
        count=4,
        _first_time="2017-06-01 08:00:00",
        id="c4ca4238a0b923820dcc509a6f75849c",
        source=tested_source,
        time="2017-06-01 08:00:00",
        _group="group2",
        until="2017-06-01 10:00:00",
    )
    group2_expected_suppressed_event = (
        "suppressed",
        group2_expected_suppressed_payload,
    )
    group3_expected_suppressed_event = (
        "suppressed",
        None,
    )

    # The namedtuple's fields are being used to describe expected
    # `HiFreqEventData` class instances' - objects containing
    # aggregated events, created during test calls to
    # the `process_new_message()` method.
    # `ExpectedHiFreqData` fields:
    # 'name': an expected name of a key of
    #   the `SourceData.groups` attribute, whose
    #   value should be the expected `HiFreqEventData` instance.
    # 'until', 'first' and 'count': fields that explicitly
    #   correspond to `HiFreqEventData` instance's attributes.
    # 'msg_index_to_payload': an index of element in the `messages`
    #   param, a dict, that is expected to be equal to a 'payload'
    #   attribute of the `HiFreqEventData` instance.
    ExpectedHiFreqData = namedtuple(
        "ExpectedHiFreqData", ("name", "until", "first", "count", "msg_index_to_payload"))


    @paramseq
    def _test_process_new_message_data(cls):
        yield param(
            messages=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
            ],
            expected_source_time=datetime.datetime(2017, 6, 1, 10),
            expected_groups=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 10),
                    first=datetime.datetime(2017, 6, 1, 10),
                    count=1,
                    msg_index_to_payload=0,
                ),
            ],
        )

        # Second message fits to specific `time_tolerance` parameter
        # for the source.
        yield param(
            messages=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": cls.other_source,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.other_source,
                    "_group": "group1",
                    "time": "2017-06-01 09:40:00",
                },
            ],
            expected_source_time=datetime.datetime(2017, 6, 1, 10),
            expected_groups=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 10),
                    first=datetime.datetime(2017, 6, 1, 10),
                    count=2,
                    msg_index_to_payload=0,
                ),
            ],
        )

        yield param(
            messages=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 12:00:00",
                },
            ],
            expected_source_time=datetime.datetime(2017, 6, 1, 12),
            expected_groups=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 10),
                    first=datetime.datetime(2017, 6, 1, 10),
                    count=1,
                    msg_index_to_payload=0,
                ),
                cls.ExpectedHiFreqData(
                    name="group2",
                    until=datetime.datetime(2017, 6, 1, 12),
                    first=datetime.datetime(2017, 6, 1, 12),
                    count=1,
                    msg_index_to_payload=1,
                ),
            ],
        )

        yield param(
            messages=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 11:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 12:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851c",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 13:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75852b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 14:00:00",
                },
            ],
            expected_source_time=datetime.datetime(2017, 6, 1, 14),
            expected_groups=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 14),
                    first=datetime.datetime(2017, 6, 1, 10),
                    count=3,
                    msg_index_to_payload=0,
                ),
                cls.ExpectedHiFreqData(
                    name="group2",
                    until=datetime.datetime(2017, 6, 1, 13),
                    first=datetime.datetime(2017, 6, 1, 12),
                    count=2,
                    msg_index_to_payload=2,
                ),
            ],
        )

        # Messages of the "group1" are aggregated until the message
        # from next day comes in. It triggers publishing of aggregated
        # messages, and a `HiFreqEventData` for "group1" events
        # is replaced by the new instance.
        # *Important*: aggregated messages of different groups
        # from the same source would also be published in this
        # situation, but it happens later, in the `Aggregator`'s
        # instance `process_event()` method.
        yield param(
            messages=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851b",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 10:15:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75751c",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 10:30:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 11:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 12:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851c",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 13:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75852b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-02 14:00:00",
                },
            ],
            expected_source_time=datetime.datetime(2017, 6, 2, 14),
            expected_groups=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 2, 14),
                    first=datetime.datetime(2017, 6, 2, 14),
                    count=1,
                    msg_index_to_payload=6,
                ),
                cls.ExpectedHiFreqData(
                    name="group2",
                    until=datetime.datetime(2017, 6, 1, 10, 30),
                    first=datetime.datetime(2017, 6, 1, 10, 15),
                    count=2,
                    msg_index_to_payload=1,
                ),
            ],
            expected_buffers=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 13),
                    first=datetime.datetime(2017, 6, 1, 10),
                    count=4,
                    msg_index_to_payload=0,
                ),
            ],
        )

        # Messages of the "group1" are aggregated until the message
        # newer by more than 12 hours (by default) is processed.
        # It triggers publishing of aggregated
        # messages, and a `HiFreqEventData` for "group1" events
        # is replaced by the new instance.
        # *Important*: aggregated messages of different groups
        # from the same source would also be published in this
        # situation, but it happens later, in the `Aggregator`'s
        # instance `process_event()` method.
        yield param(
            messages=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 07:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75751b",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 08:10:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851b",
                    "source": cls.tested_source,
                    "_group": "group2",
                    "time": "2017-06-01 08:30:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851c",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75852b",
                    "source": cls.tested_source,
                    "_group": "group1",
                    "time": "2017-06-01 22:00:01",
                },
            ],
            expected_source_time=datetime.datetime(2017, 6, 1, 22, 0, 1),
            expected_groups=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 22, 0, 1),
                    first=datetime.datetime(2017, 6, 1, 22, 0, 1),
                    count=1,
                    msg_index_to_payload=6,
                ),
                cls.ExpectedHiFreqData(
                    name="group2",
                    until=datetime.datetime(2017, 6, 1, 8, 30),
                    first=datetime.datetime(2017, 6, 1, 8, 10),
                    count=2,
                    msg_index_to_payload=2,
                ),
            ],
            expected_buffers=[
                cls.ExpectedHiFreqData(
                    name="group1",
                    until=datetime.datetime(2017, 6, 1, 10),
                    first=datetime.datetime(2017, 6, 1, 7),
                    count=4,
                    msg_index_to_payload=0,
                ),
            ],
        )


    @paramseq
    def _test_generate_suppressed_events_for_source_data(cls):
        # The newest message is from the next day comparing
        # to previous events from "group1" and "group2",
        # "suppressed" events for both groups should be
        # generated. Data for the "group3" is None,
        # because the group has only one event.
        yield param(
            new_message={
                "id": "c4ca4238a0b923820dcc509a6f75852b",
                "source": cls.tested_source,
                "_group": "group1",
                "time": "2017-06-02 10:00:01",
            },
            expected_results=[
                cls.group1_expected_suppressed_event,
                cls.group2_expected_suppressed_event,
                cls.group3_expected_suppressed_event,
            ],
        )

        # The newest message is more than 12 hours newer
        # than the previous event of the "group1", but not
        # the event of the "group2" - a "suppressed" event
        # should be generated only of the "group1". Because
        # of the "group2" not meeting the condition - checks
        # of next groups are not performed.
        yield param(
            new_message={
                "id": "c4ca4238a0b923820dcc509a6f75852b",
                "source": cls.tested_source,
                "_group": "group1",
                "time": "2017-06-01 21:10:00",
            },
            expected_results=[
                cls.group1_expected_suppressed_event,
            ],
        )

        # The newest message is more than 12 hours newer
        # than the previous event of both groups, "suppressed"
        # events should be generated for "group1" and "group2".
        # Data for the "group3" is None, because the group
        # has only one event.
        yield param(
            new_message={
                "id": "c4ca4238a0b923820dcc509a6f75852b",
                "source": cls.tested_source,
                "_group": "group1",
                "time": "2017-06-01 22:10:00",
            },
            expected_results=[
                cls.group1_expected_suppressed_event,
                cls.group2_expected_suppressed_event,
                cls.group3_expected_suppressed_event,
            ],
        )


    @paramseq
    def _test_generate_suppressed_events_after_timeout_data(cls):
        # more than 24 hours has passed since processing of last
        # event for the source "testprovider.testchannel"
        yield param(
            mocked_utcnow=datetime.datetime(2017, 6, 2, 15),
            expected_inactive_sources=[
                cls.tested_source,
            ],
        )

        # more than 24 hours has passed since processing of last
        # event for both sources
        yield param(
            mocked_utcnow=datetime.datetime(2017, 6, 2, 20, 2),
            expected_inactive_sources=[
                cls.tested_source,
                cls.other_source,
            ],
        )

        # more than 24 hours has not passed for any of tested sources
        yield param(
            mocked_utcnow=datetime.datetime(2017, 6, 2, 14),
            expected_inactive_sources=[],
        )

    def setUp(self):
        self._adw = AggregatorDataManager.__new__(AggregatorDataManager)

        self._adw.aggr_data_fac = FileAccessor(self.sample_aggr_data_path)
        self._adw.aggr_data_fac.path.unlink(missing_ok=True)

        self._adw.payload_storage_fac = FileAccessor(
            self._adw.aggr_data_fac.path.with_suffix('.payload-storage'),
        )
        self._adw.payload_storage_fac.path.unlink(missing_ok=True)

        self._adw.aggr_data = AggregatorData()
        self._adw.payload_storage = PayloadStorage(self._adw.payload_storage_fac.path)
        self.addCleanup(lambda: self._adw.payload_storage.close())
        self._adw.payload_storage.associate_with_aggr_data(self._adw.aggr_data)

        self._adw.time_tolerance = datetime.timedelta(seconds=self.sample_time_tolerance)
        self._adw.time_tolerance_per_source = {
            source: datetime.timedelta(seconds=time_tolerance)
            for source, time_tolerance in self.sample_time_tolerance_per_source.items()}

    def test_store_restore_state(self):
        """
        Check validity of data stored in Pickle object and saved as temporary files
        comparing its restored state.
        """
        message = {
            "id": "c4ca4238a0b923820dcc509a6f75852b",
            "source": self.tested_source,
            "_group": "group1",
            "time": "2017-06-01 22:10:00",
        }
        expected_stored_message = message.copy()

        # process an example message
        self._adw.process_new_message(message)
        # assert the aggregator data file does not exist yet
        self.assertFalse(self.sample_aggr_data_path.exists())
        # store the state
        self._adw.store_state()
        # assert the aggregator data file exists
        self.assertTrue(self.sample_aggr_data_path.is_file())
        # erase state attributes
        self._adw.aggr_data = None
        self._adw.payload_storage = None
        # restore the state
        self._adw.restore_state()
        # check the state
        event = self._adw.aggr_data.sources[self.tested_source].groups["group1"]
        self.assertEqual(event.count, 1)
        self.assertEqual(event._initial_payload, expected_stored_message)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 1)

        # assert the exception is being raised when trying to store
        # the state, but cannot write to the path
        self.sample_aggr_data_path.unlink()
        self.sample_aggr_data_path.mkdir()
        with self.assertRaises(IsADirectoryError):
            self._adw.store_state()

        self._adw.aggr_data = None
        self._adw.payload_storage = None

        # assert the warning is being logged when trying to restore
        # the state from a non-existent file
        self.sample_aggr_data_path.rmdir()
        with self.assertLogs(level='WARNING') as patched_logger:
            self._adw.restore_state()
        self.assertEqual(patched_logger.output, [
            f"WARNING:n6datapipeline.aggregator:The aggregator data "
            f"file does not exist (FileNotFoundError: [Errno 2] No such "
            f"file or directory: {str(self.sample_aggr_data_path)!a}). "
            f"Initializing a new empty state..."
        ])

    def test_store_restore_maintain_state(self):
        message_1 = {
            "id": "c4ca4238a0b923820dcc509a6f75852b",
            "source": self.tested_source,
            "_group": "group_1",
            "time": "2017-06-01 22:10:00",
        }
        message_1_bis = {
            "id": "00112233445566778899aabbccddeeff",
            "source": self.tested_source,
            "_group": "group_1",
            "time": "2017-06-01 22:10:20",
        }
        message_2 = {
            "id": "0123456789abcdef0123456789abcdef",
            "source": self.other_source,
            "_group": "group_2",
            "time": "2025-07-14 03:16:11",
        }
        message_3 = {
            "id": "33333333333333333333333333333333",
            "source": self.other_source,
            "_group": "group_3",
            "time": "2025-07-14 03:31:59",
        }
        message_4 = {
            "id": "44444444444444444444444444444444",
            "source": self.tested_source,
            "_group": "group_4",
            "time": "2025-07-14 03:34:01",
        }
        message_5 = {
            "id": "55555555555555555555555555555555",
            "source": self.tested_source,
            "_group": "group_5",
            "time": "2025-07-14 03:34:01",
        }
        expected_stored_message_1 = message_1.copy()
        expected_stored_message_2 = message_2.copy()
        expected_stored_message_3 = message_3.copy()
        expected_stored_message_4 = message_4.copy()
        expected_stored_message_5 = message_5.copy()

        self.assertEqual(len(self._adw.aggr_data.payload_handles), 0)

        # process example messages
        self._adw.process_new_message(message_1)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 1)
        self._adw.process_new_message(message_2)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 2)
        # ...and immediately check the state...
        event_1 = self._adw.aggr_data.sources[self.tested_source].groups["group_1"]
        self.assertEqual(event_1.count, 1)
        self.assertEqual(event_1._initial_payload, expected_stored_message_1)
        event_2 = self._adw.aggr_data.sources[self.other_source].groups["group_2"]
        self.assertEqual(event_2.count, 1)
        self.assertEqual(event_2._initial_payload, expected_stored_message_2)
        # ...including also the payload handles
        payload_1_handle = self._adw.aggr_data.payload_handles[0]
        payload_2_handle = self._adw.aggr_data.payload_handles[1]
        self.assertEqual(payload_1_handle.load(), expected_stored_message_1)
        self.assertEqual(payload_2_handle.load(), expected_stored_message_2)
        self.assertEqual(payload_1_handle.offset, 0)
        self.assertGreater(payload_2_handle.offset, payload_1_handle.offset)

        # store the state
        self._adw.store_state()
        # erase state attributes
        self._adw.aggr_data = None
        self._adw.payload_storage = None
        # restore the state
        self._adw.restore_state()
        # ...and immediately check some payload handles
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 2)

        # do the maintenance of the state
        self._adw.maintain_state(shall_shrink=True)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 2)

        # check the state...
        event_1 = self._adw.aggr_data.sources[self.tested_source].groups["group_1"]
        self.assertEqual(event_1.count, 1)
        self.assertEqual(event_1._initial_payload, expected_stored_message_1)
        event_2 = self._adw.aggr_data.sources[self.other_source].groups["group_2"]
        self.assertEqual(event_2.count, 1)
        self.assertEqual(event_2._initial_payload, expected_stored_message_2)
        # ...including also the payload handles
        payload_1_handle = self._adw.aggr_data.payload_handles[0]
        payload_2_handle = self._adw.aggr_data.payload_handles[1]
        self.assertEqual(payload_1_handle.load(), expected_stored_message_1)
        self.assertEqual(payload_2_handle.load(), expected_stored_message_2)
        self.assertEqual(payload_1_handle.offset, 0)
        self.assertGreater(payload_2_handle.offset, payload_1_handle.offset)

        # process other example messages
        self._adw.process_new_message(message_1_bis)
        self._adw.process_new_message(message_3)
        self._adw.process_new_message(message_4)
        self._adw.process_new_message(message_5)
        # ...and immediately check some payload handles
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 5)
        payload_4_handle = self._adw.aggr_data.payload_handles[3]
        payload_5_handle = self._adw.aggr_data.payload_handles[4]
        self.assertEqual(payload_4_handle.load(), expected_stored_message_4)
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        payload_4_offset_a = payload_4_handle.offset
        payload_5_offset_a = payload_5_handle.offset
        self.assertGreater(payload_5_offset_a, payload_4_offset_a)

        # simulate finishing processing one of the newly added groups
        del self._adw.aggr_data.sources[self.tested_source].groups["group_4"]

        # store the state
        self._adw.store_state()
        # erase state attributes
        self._adw.aggr_data = None
        self._adw.payload_storage = None
        # restore the state
        self._adw.restore_state()
        # ...and immediately check some payload handles
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 5)
        payload_4_handle = self._adw.aggr_data.payload_handles[3]
        payload_5_handle = self._adw.aggr_data.payload_handles[4]
        self.assertEqual(payload_4_handle.offset, payload_4_offset_a)
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        self.assertEqual(payload_5_handle.offset, payload_5_offset_a)

        # do the maintenance of the state
        self._adw.maintain_state(shall_shrink=True)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 4)

        # check the state...
        self.assertNotIn("group_4", self._adw.aggr_data.sources[self.tested_source].groups)
        event_1 = self._adw.aggr_data.sources[self.tested_source].groups["group_1"]
        self.assertEqual(event_1.count, 2)
        self.assertEqual(event_1._initial_payload, expected_stored_message_1)
        event_2 = self._adw.aggr_data.sources[self.other_source].groups["group_2"]
        self.assertEqual(event_2.count, 1)
        self.assertEqual(event_2._initial_payload, expected_stored_message_2)
        event_3 = self._adw.aggr_data.sources[self.other_source].groups["group_3"]
        self.assertEqual(event_3.count, 1)
        self.assertEqual(event_3._initial_payload, expected_stored_message_3)
        event_5 = self._adw.aggr_data.sources[self.tested_source].groups["group_5"]
        self.assertEqual(event_5.count, 1)
        self.assertEqual(event_5._initial_payload, expected_stored_message_5)
        # ...including some payload handles
        payload_3_handle = self._adw.aggr_data.payload_handles[2]
        payload_5_handle = self._adw.aggr_data.payload_handles[3]
        self.assertEqual(payload_3_handle.load(), expected_stored_message_3)
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        payload_3_offset = payload_3_handle.offset
        payload_5_offset_b = payload_5_handle.offset
        self.assertLess(payload_5_offset_b, payload_5_offset_a)
        self.assertGreater(payload_5_offset_b, payload_3_offset)

        # simulate finishing processing some other groups
        del self._adw.aggr_data.sources[self.other_source].groups["group_2"]
        del self._adw.aggr_data.sources[self.other_source].groups["group_3"]

        # store the state
        self._adw.store_state()
        # erase state attributes
        self._adw.aggr_data = None
        self._adw.payload_storage = None
        # restore the state
        self._adw.restore_state()
        # ...and immediately check some payload handles
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 4)
        payload_3_handle = self._adw.aggr_data.payload_handles[2]
        payload_5_handle = self._adw.aggr_data.payload_handles[3]
        self.assertEqual(payload_3_handle.offset, payload_3_offset)
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        self.assertEqual(payload_5_handle.offset, payload_5_offset_b)

        # do the maintenance of the state
        self._adw.maintain_state(shall_shrink=True)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 2)

        # check the state...
        self.assertNotIn("group_2", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertNotIn("group_3", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertNotIn("group_4", self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertTrue(self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertFalse(self._adw.aggr_data.sources[self.other_source].groups)
        event_1 = self._adw.aggr_data.sources[self.tested_source].groups["group_1"]
        self.assertEqual(event_1.count, 2)
        self.assertEqual(event_1._initial_payload, expected_stored_message_1)
        event_5 = self._adw.aggr_data.sources[self.tested_source].groups["group_5"]
        self.assertEqual(event_5.count, 1)
        self.assertEqual(event_5._initial_payload, expected_stored_message_5)
        # ...including some payload handle
        payload_5_handle = self._adw.aggr_data.payload_handles[1]
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        payload_5_offset_c = payload_5_handle.offset
        self.assertLess(payload_5_offset_c, payload_5_offset_b)

        # simulate finishing processing yet another group
        del self._adw.aggr_data.sources[self.tested_source].groups["group_1"]

        # store the state
        self._adw.store_state()
        # erase state attributes
        self._adw.aggr_data = None
        self._adw.payload_storage = None
        # restore the state
        self._adw.restore_state()
        # ...and immediately check some payload handle
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 2)
        payload_5_handle = self._adw.aggr_data.payload_handles[1]
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        self.assertEqual(payload_5_handle.offset, payload_5_offset_c)
        self.assertGreater(payload_5_handle.offset, 0)

        # do the maintenance of the state, but this time with `shall_shrink=False`
        self._adw.maintain_state(shall_shrink=False)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 2)

        # check the state...
        self.assertNotIn("group_1", self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertNotIn("group_2", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertNotIn("group_3", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertNotIn("group_4", self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertTrue(self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertFalse(self._adw.aggr_data.sources[self.other_source].groups)
        event_5 = self._adw.aggr_data.sources[self.tested_source].groups["group_5"]
        self.assertEqual(event_5.count, 1)
        self.assertEqual(event_5._initial_payload, expected_stored_message_5)
        # ...including some payload handle
        payload_5_handle = self._adw.aggr_data.payload_handles[1]
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        self.assertEqual(payload_5_handle.offset, payload_5_offset_c)
        self.assertGreater(payload_5_handle.offset, 0)

        # do the maintenance of the state again, now normally (with `shall_shrink=True`)
        self._adw.maintain_state(shall_shrink=True)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 1)

        # check the state...
        self.assertNotIn("group_1", self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertNotIn("group_2", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertNotIn("group_3", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertNotIn("group_4", self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertTrue(self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertFalse(self._adw.aggr_data.sources[self.other_source].groups)
        event_5 = self._adw.aggr_data.sources[self.tested_source].groups["group_5"]
        self.assertEqual(event_5.count, 1)
        self.assertEqual(event_5._initial_payload, expected_stored_message_5)
        # ...including some payload handle
        payload_5_handle = self._adw.aggr_data.payload_handles[0]
        self.assertEqual(payload_5_handle.load(), expected_stored_message_5)
        self.assertEqual(payload_5_handle.offset, 0)

        # simulate finishing processing the last group
        del self._adw.aggr_data.sources[self.tested_source].groups["group_5"]

        # store the state
        self._adw.store_state()
        # erase state attributes
        self._adw.aggr_data = None
        self._adw.payload_storage = None
        # restore the state
        self._adw.restore_state()
        # ...and immediately check some payload handle
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 1)
        payload_5_handle = self._adw.aggr_data.payload_handles[0]
        self.assertEqual(payload_5_handle.offset, 0)

        # do the maintenance of the state
        self._adw.maintain_state(shall_shrink=True)
        self.assertEqual(len(self._adw.aggr_data.payload_handles), 0)

        # check the state
        self.assertFalse(self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertFalse(self._adw.aggr_data.sources[self.other_source].groups)

    @foreach(_test_process_new_message_data)
    def test_process_new_message(self, messages, expected_source_time,
                                 expected_groups, expected_buffers=None):
        """
        Check validity of data inside tested source's `groups`
        and `buffer` attributes after processing of consecutive
        messages.
        """
        test_sources = []
        with patch("n6datapipeline.aggregator.datetime") as datetime_mock:
            datetime_mock.datetime.utcnow.return_value = self.mocked_utcnow
            datetime_mock.datetime.side_effect = (lambda *args, **kw:
                                                  datetime.datetime(*args, **kw))
            # a `SourceData` attribute `time_tolerance` needs
            # a `datetime.timedelta` instance, but it is mocked now
            datetime_mock.timedelta.side_effect = (lambda *args, **kw:
                                                   datetime.timedelta(*args, **kw))

            # actual calls
            for msg in messages:
                self._adw.process_new_message(msg)
                if msg["source"] not in test_sources:
                    test_sources.append(msg["source"])

            for test_source in test_sources:
                # assertions for the source
                created_source = self._adw.aggr_data.sources[test_source]
                self.assertEqual(created_source.last_active, self.mocked_utcnow)
                self.assertEqual(created_source.time, expected_source_time)
                self.assertEqual(len(expected_groups), len(created_source.groups))

                # assertions for groups
                for expected_group in expected_groups:
                    self.assertIn(expected_group.name, created_source.groups)
                    created_group = created_source.groups[expected_group.name]
                    self.assertIsInstance(created_group, HiFreqEventData)
                    self.assertEqual(expected_group.until, created_group.until)
                    self.assertEqual(expected_group.first, created_group.first)
                    self.assertEqual(expected_group.count, created_group.count)
                    self.assertEqual(
                        messages[expected_group.msg_index_to_payload],
                        created_group._initial_payload)
                    # assertions for potential buffers
                    if expected_buffers:
                        for expected_buffer in expected_buffers:
                            created_buffer = created_source.buffer[expected_buffer.name]
                            self.assertEqual(expected_buffer.until, created_buffer.until)
                            self.assertEqual(expected_buffer.first, created_buffer.first)
                            self.assertEqual(expected_buffer.count, created_buffer.count)
                            self.assertEqual(
                                messages[expected_buffer.msg_index_to_payload],
                                created_buffer._initial_payload)


    @foreach(_test_generate_suppressed_events_for_source_data)
    def test_generate_suppressed_events_for_source(self, new_message, expected_results):
        """
        Check, if "suppressed" events are generated when a newly
        processed message's time is greater than its group's `until`
        time by the specified timeout (12 hours by default), or
        the message is from another day.
        """
        tested_source_data = self._get_source_data_for_suppressed_events_tests(
            self.tested_source)
        another_source_data = self._get_source_data_for_suppressed_events_tests(
            self.other_source)
        hifreq_new_data = HiFreqEventData(new_message)
        tested_source_data.groups["group1"] = hifreq_new_data
        # `time` attribute should be equal to last message's
        tested_source_data.time = datetime.datetime.strptime(
            new_message["time"], "%Y-%m-%d %H:%M:%S")
        another_source_data.time = datetime.datetime(2017, 6, 1, 10)
        # `last_active` attribute is not relevant for the test
        tested_source_data.last_active = datetime.datetime(2017, 6, 2, 20)
        another_source_data.last_active = datetime.datetime(2017, 6, 2, 20)
        self._adw.aggr_data.sources[self.tested_source] = tested_source_data
        self._adw.aggr_data.sources[self.other_source] = another_source_data

        generated_events = list(self._adw.generate_suppressed_events_for_source(new_message))
        self.assertCountEqual(expected_results, generated_events)
        # new `HiFreqEventData` object of the "group1" should be
        # in `groups` attribute, but not in `buffer` - suppressed
        # event of the "group1" should have been generated
        self.assertIn(
            "group1", self._adw.aggr_data.sources[self.tested_source].groups)
        self.assertNotIn(
            "group1", self._adw.aggr_data.sources[self.tested_source].buffer)
        # if aggregated events of the "group2" were generated, then
        # there should not be any `HiFreqEventData` objects of this
        # group in `groups` nor `buffer` attribute
        if self.group2_expected_suppressed_event in expected_results:
            self.assertNotIn(
                "group2", self._adw.aggr_data.sources[self.tested_source].groups)
            self.assertNotIn(
                "group2", self._adw.aggr_data.sources[self.tested_source].buffer)

        # check if the other source's elements, for which suppressed
        # events were not generated, are unchanged
        self.assertIn(
            "group2", self._adw.aggr_data.sources[self.other_source].groups)
        self.assertIn(
            "group1", self._adw.aggr_data.sources[self.other_source].buffer)


    @foreach(_test_generate_suppressed_events_after_timeout_data)
    def test_generate_suppressed_events_after_timeout(self,
                                                      mocked_utcnow,
                                                      expected_inactive_sources):
        """
        Test, whether sources are treated as inactive after specified
        timeout, and if proper suppressed events are generated
        for them.
        """
        tested_source_data = self._get_source_data_for_suppressed_events_tests(
            self.tested_source)
        another_source_data = self._get_source_data_for_suppressed_events_tests(
            self.other_source)
        # `time` attribute should be equal to last message's
        tested_source_data.time = datetime.datetime(2017, 6, 1, 10)
        another_source_data.time = datetime.datetime(2017, 6, 1, 10)
        tested_source_data.last_active = datetime.datetime(2017, 6, 1, 14)
        another_source_data.last_active = datetime.datetime(2017, 6, 1, 20)
        self._adw.aggr_data.sources[self.tested_source] = tested_source_data
        self._adw.aggr_data.sources[self.other_source] = another_source_data

        source_to_expected_events = self._get_source_to_expected_events_mapping()

        with patch("n6datapipeline.aggregator.datetime") as datetime_mock:
            datetime_mock.datetime.utcnow.return_value = mocked_utcnow
            datetime_mock.datetime.side_effect = (lambda *args, **kw:
                                                  datetime.datetime(*args, **kw))
            # a `SourceData` attribute `time_tolerance` needs
            # a `datetime.timedelta` instance, but it is mocked now
            datetime_mock.timedelta.side_effect = (lambda *args, **kw:
                                                   datetime.timedelta(*args, **kw))
            # actual call
            generated_events = list(self._adw.generate_suppressed_events_after_timeout())
            expected_events = [event for source, vals in source_to_expected_events.items()
                               if source in expected_inactive_sources for event in vals]
            self.assertEqual(expected_events, generated_events)

            for source in self.sources_tested_for_inactivity:
                # check if `groups` and `buffers` were cleared
                # for inactive sources
                if source in expected_inactive_sources:
                    self.assertFalse(self._adw.aggr_data.sources[source].groups)
                    self.assertFalse(self._adw.aggr_data.sources[source].buffer)
                # make sure `groups` and `buffers` were intact
                # for still active sources
                else:
                    self.assertTrue(self._adw.aggr_data.sources[source].groups)
                    self.assertTrue(self._adw.aggr_data.sources[source].buffer)


    # helper methods
    def _get_source_data_for_suppressed_events_tests(self, source_name):
        source_data = SourceData(self._get_time_tolerance_from_source(source_name))

        group1_hifreq_buffered_data_payload = {
            "id": "c4ca4238a0b923820dcc509a6f75849b",
            "source": source_name,
            "_group": "group1",
            "time": "2017-06-01 07:00:00",
        }
        group1_hifreq_buffered_data = HiFreqEventData(group1_hifreq_buffered_data_payload)
        assert group1_hifreq_buffered_data._initial_payload == group1_hifreq_buffered_data_payload
        assert group1_hifreq_buffered_data.first == datetime.datetime(2017, 6, 1, 7)
        group1_hifreq_buffered_data.until = datetime.datetime(2017, 6, 1, 9)
        group1_hifreq_buffered_data.count = 5
        source_data.buffer["group1"] = group1_hifreq_buffered_data

        group2_hifreq_data_payload = {
            "id": "c4ca4238a0b923820dcc509a6f75849c",
            "source": source_name,
            "_group": "group2",
            "time": "2017-06-01 08:00:00",
        }
        group2_hifreq_data = HiFreqEventData(group2_hifreq_data_payload)
        assert group2_hifreq_data._initial_payload == group2_hifreq_data_payload
        assert group2_hifreq_data.first == datetime.datetime(2017, 6, 1, 8)
        group2_hifreq_data.until = datetime.datetime(2017, 6, 1, 10)
        group2_hifreq_data.count = 4
        source_data.groups["group2"] = group2_hifreq_data

        group3_payload = {
            "id": "c4ca4238a0b923820dcc509a6f75849d",
            "source": source_name,
            "_group": "group3",
            "time": "2017-06-01 07:30:00",
        }
        group3_hifreq_data = HiFreqEventData(group3_payload)
        source_data.groups["group3"] = group3_hifreq_data

        return source_data

    def _get_source_to_expected_events_mapping(self):
        group1_other_source_payload = self.group1_expected_suppressed_payload.copy()
        group1_other_source_payload["source"] = self.other_source
        group1_other_source_event = ("suppressed", group1_other_source_payload)
        group2_other_source_payload = self.group2_expected_suppressed_payload.copy()
        group2_other_source_payload["source"] = self.other_source
        group2_other_source_event = ("suppressed", group2_other_source_payload)
        group3_other_source_event = self.group3_expected_suppressed_event
        return {
            self.tested_source: [
                self.group1_expected_suppressed_event,
                self.group2_expected_suppressed_event,
                self.group3_expected_suppressed_event,
            ],
            self.other_source: [
                group1_other_source_event,
                group2_other_source_event,
                group3_other_source_event,
            ],
        }

    def _get_time_tolerance_from_source(self, source):
        return datetime.timedelta(seconds=(
            self.sample_time_tolerance_per_source.get(source) or self.sample_time_tolerance))


class TestAggregatorData(unittest.TestCase):

    sample_source = "testprovider.testchannel"
    sample_other_source = "otherprovider.otherchannel"
    sample_group = "group1"
    sample_other_group = "group2"
    sample_time_tolerance = 500
    sample_time_tolerance_per_source = {
        sample_other_source: 1000,
    }

    @cached_property
    def groups_hifreq_data(self):
        return HiFreqEventData(
            {
                "id": "c4ca4238a0b923820dcc509a6f75849c",
                "source": self.sample_source,
                "_group": self.sample_group,
                "time": "2017-06-02 12:00:00",
            }
        )

    @cached_property
    def buffer_hifreq_data(self):
        return HiFreqEventData(
            {
                "id": "c4ca4238a0b923820dcc509a6f75849b",
                "source": self.sample_source,
                "_group": self.sample_group,
                "time": "2017-06-01 10:00:00",
            }
        )

    def setUp(self):
        self._payload_storage = PayloadStorage._make_for_tests()
        self.addCleanup(self._payload_storage.close)
        self._aggregator_data = AggregatorData()
        self._sample_source_data = SourceData(
            datetime.timedelta(seconds=self.sample_time_tolerance))
        self._sample_source_data.time = datetime.datetime(2017, 6, 2, 12)
        self._sample_source_data.last_active = datetime.datetime(2017, 6, 2, 13)
        self._sample_source_data.groups[self.sample_group] = self.groups_hifreq_data
        self._sample_source_data.buffer[self.sample_group] = self.buffer_hifreq_data
        self._aggregator_data.sources[self.sample_source] = self._sample_source_data

    def test_create_new_source_data(self):
        source_data = self._aggregator_data.get_or_create_sourcedata(
            {
                "id": "c4ca4238a0b923820dcc509a6f75851d",
                "source": self.sample_other_source,
                "_group": self.sample_group,
                "time": "2017-05-01 12:00:00",
            },
            self._get_time_tolerance_from_source(self.sample_other_source))
        self.assertIsInstance(source_data, SourceData)
        self.assertEqual(source_data.time, None)
        self.assertEqual(source_data.last_active, None)
        self.assertFalse(source_data.groups)
        self.assertFalse(source_data.buffer)
        self.assertEqual(
            source_data.time_tolerance,
            self._get_time_tolerance_from_source(self.sample_other_source))
        self.assertIs(source_data, self._aggregator_data.sources[self.sample_other_source])

    def test_get_existing_source_data(self):
        source_data = self._aggregator_data.get_or_create_sourcedata(
            {
                "id": "c4ca4238a0b923820dcc509a6f75860f",
                "source": self.sample_source,
                "_group": self.sample_other_group,
                "time": "2017-05-01 12:00:00",
            },
            self._get_time_tolerance_from_source(self.sample_other_source))
        self.assertIsInstance(source_data, SourceData)
        self.assertEqual(source_data.time, self._sample_source_data.time)
        self.assertEqual(source_data.last_active, self._sample_source_data.last_active)
        self.assertEqual(
            source_data.time_tolerance,
            self._get_time_tolerance_from_source(self.sample_source))
        self.assertIn(self.sample_group, source_data.groups)
        self.assertIn(self.sample_group, source_data.buffer)
        self.assertEqual(1, len(source_data.groups))
        self.assertEqual(1, len(source_data.buffer))
        self.assertEqual(self.groups_hifreq_data, source_data.groups[self.sample_group])
        self.assertEqual(self.buffer_hifreq_data, source_data.buffer[self.sample_group])
        self.assertIs(source_data, self._aggregator_data.sources[self.sample_source])

    def _get_time_tolerance_from_source(self, source):
        return datetime.timedelta(seconds=(
            self.sample_time_tolerance_per_source.get(source) or self.sample_time_tolerance))

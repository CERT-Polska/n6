# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import datetime
import json
import os
import tempfile
import unittest
from collections import namedtuple

from mock import (
    MagicMock,
    patch,
)
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6.base.queue import n6QueueProcessingException
from n6.utils.aggregator import (
    Aggregator,
    AggregatorData,
    AggregatorDataWrapper,
    HiFreqEventData,
    SourceData,
)
from n6lib.unit_test_helpers import TestCaseMixin



@expand
class TestAggregator(TestCaseMixin, unittest.TestCase):

    sample_routing_key = "testsource.testchannel"
    sample_dbpath = "/tmp/sample_dbfile"
    sample_time_tolerance = 600
    sample_time_tolerance_per_source = {
        'anothersource.andchannel': 1200,
    }
    starting_datetime = datetime.datetime(2017, 6, 1, 10)
    mocked_utcnow = datetime.datetime(2017, 7, 1, 7, 0, 0)
    input_callback_proper_msg = (
        '{'
        '"source": "testsource.testchannel",'
        '"_group": "group1",'
        '"id": "d41d8cd98f00b204e9800998ecf8427b",'
        '"time": "2017-06-01 10:00:00"'
        '}'
    )
    input_callback_msg_no__group = (
        '{'
        '"source": "testsource.testchannel",'
        '"id": "d41d8cd98f00b204e9800998ecf8427b",'
        '"time": "2017-06-01 10:00:00"'
        '}'
    )
    mocked_config = {
        "aggregator": {
            "dbpath": sample_dbpath,
            "time_tolerance": str(sample_time_tolerance),
            "time_tolerance_per_source": json.dumps(sample_time_tolerance_per_source),
        }
    }


    @paramseq
    def _ordered_data_to_process(cls):
        # Three events are published, each one of a different group.
        yield param(
            input_data=[
                {
                    "id": "c4ca4238a0b923820dcc509a6f75849b",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "c81e728d9d4c2f636f067f89cc14862c",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "eccbc87e4b5ce2fe28308fd9f2a7baf3",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "c81e728d9d4c2f636f067f89cc14862c",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426f",
                    "source": "testsource.testchannel",
                    "_group": "group3",
                    "time": str(cls.starting_datetime),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427a",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=1)),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=1)),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": str(cls.starting_datetime + datetime.timedelta(hours=2)),
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
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
                    "id": "1",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "2",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": "2017-06-01 08:02:00",
                },
                {
                    "id": "3",
                    "source": "testsource.testchannel",
                    "_group": "group3",
                    "time": "2017-06-01 08:04:00",
                },
                {
                    "id": "4",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "5",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": "2017-06-01 09:00:20",
                },
                {
                    "id": "6",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "7",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 21:30:00",
                },
            ],
            expected_ids_to_single_events=[
                "1",
                "2",
                "3",
            ],
            expected_ids_to_suppressed_events={
                "2": {
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 01:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:01',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 01:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 02:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 18:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 20:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 18:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8425c",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:28:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 20:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 12:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 11:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
            expected_last_event_dt_updates=3,
        )

        # The second event is older than the current time, but it is
        # within the time tolerance, so it is still aggregated.
        yield param(
            input_data=[
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427b",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:51:00",  # time within mocked time tolerance
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "id": "1",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "2",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:51:00",  # within time tolerance
                },
                {
                    "id": "3",
                    "source": "anothersource.andchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:00',
                },
                {
                    "id": "4",
                    "source": "anothersource.andchannel",
                    "_group": "group1",
                    "time": '2017-06-01 10:40:00',   # within time tolerance
                },
            ],
            expected_ids_to_single_events=[
                "1",
                "3",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 17:00:00",
                },
                {
                    "id": "53b325261706c63aed655a3ca8810780",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 18:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427f",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 23:57:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 17:00:00",
                },
                {
                    "id": "53b325261706c63aed655a3ca8810780",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 18:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427c",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 19:00:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427f",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": '2017-06-01 23:57:00',
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
            ],
            # Number of times the `SourceData` instance's `last_event`
            # datetime is expected to be updated. It should not be
            # updated, if the event is out of order.
            expected_last_event_dt_updates=2,
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
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427d",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8426d",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998ecf8427e",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": '2017-06-01 11:00:02',
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998ecf8427b",
            ],
            expected_last_event_dt_updates=2,
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
                    "id": "d41d8cd98f00b204e9800998hg351",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 00:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg352",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 23:51:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg353",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": "2020-01-02 00:01:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg354",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-02 00:00:00",
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998hg351",
                "d41d8cd98f00b204e9800998hg352",
                "d41d8cd98f00b204e9800998hg353",
            ],
            expected_last_event_dt_updates=3,
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
                    "id": "d41d8cd98f00b204e9800998hg351",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 22:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg352",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 23:51:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg353",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": "2020-01-02 00:01:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg354",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-02 00:00:00",
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998hg351",
                "d41d8cd98f00b204e9800998hg353",
            ],
            expected_last_event_dt_updates=3,
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
                    "id": "d41d8cd98f00b204e9800998hg351",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 00:00:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg352",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-01 20:51:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg353",
                    "source": "testsource.testchannel",
                    "_group": "group2",
                    "time": "2020-01-02 22:01:00",
                },
                {
                    "id": "d41d8cd98f00b204e9800998hg354",
                    "source": "testsource.testchannel",
                    "_group": "group1",
                    "time": "2020-01-02 22:00:00",
                },
            ],
            expected_ids_to_single_events=[
                "d41d8cd98f00b204e9800998hg351",
                "d41d8cd98f00b204e9800998hg352",
                "d41d8cd98f00b204e9800998hg353",
                "d41d8cd98f00b204e9800998hg354",
            ],
            expected_last_event_dt_updates=4,
        )

    def setUp(self):
        self._published_events = []
        self._aggregator = Aggregator.__new__(Aggregator)
        aggr_data_wrapper = AggregatorDataWrapper.__new__(AggregatorDataWrapper)
        aggr_data_wrapper.aggr_data = AggregatorData()
        aggr_data_wrapper.time_tolerance = self.sample_time_tolerance
        aggr_data_wrapper.time_tolerance_per_source = self.sample_time_tolerance_per_source
        self._mocked_datetime_counter = 0
        self._aggregator.db = aggr_data_wrapper


    @foreach(_ordered_data_to_process
             + _unordered_data_to_process_event__buffer_may_contain_suppressed_event_1
             + _unordered_data_to_process_event__buffer_may_contain_suppressed_event_2
             + _unordered_data_to_process_event__buffer_may_contain_suppressed_event_3)
    def test_processing_events(self,
                               input_data,
                               expected_ids_to_single_events=None,
                               expected_ids_to_suppressed_events=None,
                               expected_last_event_dt_updates=None):

        if expected_last_event_dt_updates is None:
            expected_last_event_dt_updates = len(input_data)

        self._test_process_event(input_data,
                                 expected_ids_to_single_events,
                                 expected_ids_to_suppressed_events,
                                 expected_last_event_dt_updates)


    @foreach(_unordered_data_to_process)
    def test_processing_unordered_events(self,
                                         input_data,
                                         expected_ids_to_single_events=None,
                                         expected_ids_to_suppressed_events=None,
                                         expected_last_event_dt_updates=None):

        if expected_last_event_dt_updates is None:
            expected_last_event_dt_updates = len(input_data)

        with self.assertRaisesRegexp(n6QueueProcessingException, r"\bEvent out of order\b"):
            self._test_process_event(input_data,
                                     expected_ids_to_single_events,
                                     expected_ids_to_suppressed_events,
                                     expected_last_event_dt_updates)

    @foreach([
        param(
            count=32767,
            expected_body_content={
                "source": "ham.spam",
                "type": "foobar",
                "count": 32767,
            },
        ).label("count not over limit"),
        param(
            count=32768,
            expected_body_content={
                "source": "ham.spam",
                "type": "foobar",
                "count": 32767,
                "count_actual": 32768,
            },
        ).label("count over limit"),
    ])
    def test_publish_event(self, count, expected_body_content):
        type_ = "foobar"
        payload = {
            "source": "ham.spam",
            "_group": "something",
            "count": count,
        }
        data = type_, payload
        expected_routing_key = "foobar.aggregated.ham.spam"
        self._aggregator.publish_output = MagicMock()

        self._aggregator.publish_event(data)

        self.assertEqual(len(self._aggregator.publish_output.mock_calls), 1)
        publish_output_kwargs = self._aggregator.publish_output.mock_calls[0][-1]
        self.assertEqual(set(publish_output_kwargs.iterkeys()), {"routing_key", "body"})
        self.assertEqual(publish_output_kwargs["routing_key"], expected_routing_key)
        self.assertJsonEqual(publish_output_kwargs["body"], expected_body_content)


    def test_input_callback(self):
        with patch.object(Aggregator, "process_event") as process_event_mock:
            self._aggregator.input_callback("testsource.testchannel",
                                            self.input_callback_proper_msg,
                                            self.sample_routing_key)
        process_event_mock.assert_called_with(json.loads(self.input_callback_proper_msg))


    def test_input_callback_with__group_missing(self):
        with self.assertRaisesRegexp(n6QueueProcessingException, r"\bmissing '_group' field\b"):
            with patch.object(Aggregator, "process_event"):
                self._aggregator.input_callback("testsource.testchannel",
                                                self.input_callback_msg_no__group,
                                                self.sample_routing_key)

    @patch("n6.base.queue.QueuedBase.__init__", autospec=True)
    @patch("n6lib.config.Config._load_n6_config_files", return_value=mocked_config)
    def test_init_class(self, config_mock, init_mock):
        with tempfile.NamedTemporaryFile() as fp:
            config_mock.return_value["aggregator"]["dbpath"] = fp.name
            self._aggregator.__init__()

        # store dir does not exist
        with tempfile.NamedTemporaryFile() as fp, \
                self.assertRaisesRegexp(Exception, r"store dir does not exist, stop aggregator"):
            config_mock.return_value["aggregator"]["dbpath"] = os.path.join(fp.name,
                                                                            "nonexistent_file")
            self._aggregator.__init__()

        # store directory exists, but it has no rights to write
        with tempfile.NamedTemporaryFile() as fp, \
                patch("os.access", return_value=None), \
                self.assertRaisesRegexp(Exception,
                                        r"stop aggregator, remember to set the rights for user, "
                                        r"which runs aggregator"):
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
                            expected_last_event_dt_updates):
        """
        Use input data to call Aggregator's `process_event()` method;
        use it to create expected events and compare it with events
        crated based on arguments that QueuedBase's `publish_output()`
        method was called with (`publish_output()` normally, if not
        mocked, would publish actual events created from
        this arguments).
        """
        expected_events = []

        with patch("n6.utils.aggregator.datetime") as datetime_mock,\
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
        self.assertItemsEqual(expected_events, events_from_calls)
        # Check how many times datetime.datetime.utcnow() was called,
        # meaning how many times the `SourceData` instance's
        # `last_event` attribute was updated. It should not be updated
        # when the event is out of order (we assume the source was not
        # active if it published an old event).
        self.assertEqual(self._mocked_datetime_counter, expected_last_event_dt_updates)


    @staticmethod
    def _get_expected_event_from_input_data(input_data, type_):
        """
        Turn an input data to event-like dicts, that are expected
        to be created during the calls to `process_event()` method.
        Args:
            `input_data`:
                a dict with input data.
            `type_`:
                a type of event ('event' or 'suppressed').

        Returns:
            an event-like dict, that is expected to be created
            during the call to `process_event()`.
        """
        input_data.update({"type": type_})
        # final events do not contain field `_group`
        del input_data["_group"]
        return {
            "body": input_data,
            "routing_key": "{}.aggregated.{}".format(type_, input_data['source']),
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
class TestAggregatorDataWrapper(unittest.TestCase):

    tested_source_channel = "testsource.testchannel"
    other_source_channel = "othersource.otherchannel"
    sample_db_path = "/tmp/example.pickle"
    sample_time_tolerance = 600
    sample_time_tolerance_per_source = {
        other_source_channel: 1200,
    }
    mocked_utcnow = datetime.datetime(2017, 7, 1, 12, 0, 0)
    sources_tested_for_inactivity = [tested_source_channel, other_source_channel]

    group1_expected_suppressed_payload = dict(
        count=5,
        _first_time="2017-06-01 07:00:00",
        id="c4ca4238a0b923820dcc509a6f75849b",
        source=tested_source_channel,
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
        source=tested_source_channel,
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
    #   the `AggregatorDataWrapper`.`groups` attribute, whose
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
                    "source": cls.tested_source_channel,
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
                    "source": cls.other_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.other_source_channel,
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
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source_channel,
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
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850b",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 11:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source_channel,
                    "_group": "group2",
                    "time": "2017-06-01 12:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851c",
                    "source": cls.tested_source_channel,
                    "_group": "group2",
                    "time": "2017-06-01 13:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75852b",
                    "source": cls.tested_source_channel,
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
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851b",
                    "source": cls.tested_source_channel,
                    "_group": "group2",
                    "time": "2017-06-01 10:15:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75751c",
                    "source": cls.tested_source_channel,
                    "_group": "group2",
                    "time": "2017-06-01 10:30:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850b",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 11:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 12:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851c",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 13:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75852b",
                    "source": cls.tested_source_channel,
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
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 07:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850b",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 08:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75751b",
                    "source": cls.tested_source_channel,
                    "_group": "group2",
                    "time": "2017-06-01 08:10:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851b",
                    "source": cls.tested_source_channel,
                    "_group": "group2",
                    "time": "2017-06-01 08:30:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75850c",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 09:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75851c",
                    "source": cls.tested_source_channel,
                    "_group": "group1",
                    "time": "2017-06-01 10:00:00",
                },
                {
                    "id": "c4ca4238a0b923820dcc509a6f75852b",
                    "source": cls.tested_source_channel,
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
                "source": cls.tested_source_channel,
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
                "source": cls.tested_source_channel,
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
                "source": cls.tested_source_channel,
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
        # event for the source "testsource.testchannel"
        yield param(
            mocked_utcnow=datetime.datetime(2017, 6, 2, 15),
            expected_inactive_sources=[
                cls.tested_source_channel,
            ],
        )

        # more than 24 hours has passed since processing of last
        # event for both sources
        yield param(
            mocked_utcnow=datetime.datetime(2017, 6, 2, 20, 2),
            expected_inactive_sources=[
                cls.tested_source_channel,
                cls.other_source_channel,
            ],
        )

        # more than 24 hours has not passed for any of tested sources
        yield param(
            mocked_utcnow=datetime.datetime(2017, 6, 2, 14),
            expected_inactive_sources=[],
        )

    def setUp(self):
        self._adw = AggregatorDataWrapper.__new__(AggregatorDataWrapper)
        self._adw.time_tolerance = self.sample_time_tolerance
        self._adw.time_tolerance_per_source = self.sample_time_tolerance_per_source
        self._adw.dbpath = self.sample_db_path
        self._adw.aggr_data = AggregatorData()

    def test_store_restore_state(self):
        """
        Check validity of data stored in Pickle object and saved as temporary files
        comparing its restored state.
        """
        message = {
            "id": "c4ca4238a0b923820dcc509a6f75852b",
            "source": self.tested_source_channel,
            "_group": "group1",
            "time": "2017-06-01 22:10:00",
        }

        expected_stored_message = {
            "id": "c4ca4238a0b923820dcc509a6f75852b",
            "source": self.tested_source_channel,
            "_group": "group1",
            "time": "2017-06-01 22:10:00",
        }

        self._adw.process_new_message(message)
        with tempfile.NamedTemporaryFile() as fp:
            self._adw.dbpath = fp.name
            # store the state
            self._adw.store_state()
            # delete attribute with stored sources
            del self._adw.aggr_data
            # check restored state from existing file
            self._adw.restore_state()
            self.assertDictEqual(
                self._adw.aggr_data.sources[self.tested_source_channel].groups[
                    message["_group"]].payload,
                expected_stored_message)
            # assert given path exist
            self.assertTrue(self._adw.dbpath)
        # assert the exception is being raised when trying to store
        # the state, but there is no access to the given path; first,
        # make sure there actually is no access to the given path
        tmp_db_path = "/root/example.pickle"
        if not os.access(tmp_db_path, os.W_OK):
            with patch.object(self._adw, "dbpath", tmp_db_path):
                self.assertRaises(IOError, self._adw.store_state())
        # assert the exception is being raised when trying to restore
        # the state from nonexistent file; first, safely create
        # a temporary file, then close and remove it, so the path
        # most likely does not exist
        with tempfile.NamedTemporaryFile() as fp:
            tmp_db_path = fp.name
        if not os.path.exists(tmp_db_path):
            with patch.object(self._adw, "dbpath", tmp_db_path), \
                    self.assertRaisesRegexp(IOError, r"No such file or directory"):
                self._adw.restore_state()

    @foreach(_test_process_new_message_data)
    def test_process_new_message(self, messages, expected_source_time,
                                 expected_groups, expected_buffers=None):
        """
        Check validity of data inside tested source's `groups`
        and `buffer` attributes after processing of consecutive
        messages.
        """
        test_sources = []
        with patch("n6.utils.aggregator.datetime") as datetime_mock:
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
                self.assertEqual(created_source.last_event, self.mocked_utcnow)
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
                        created_group.payload)
                    # assertions for potential buffers
                    if expected_buffers:
                        for expected_buffer in expected_buffers:
                            created_buffer = created_source.buffer[expected_buffer.name]
                            self.assertEqual(expected_buffer.until, created_buffer.until)
                            self.assertEqual(expected_buffer.first, created_buffer.first)
                            self.assertEqual(expected_buffer.count, created_buffer.count)
                            self.assertEqual(
                                messages[expected_buffer.msg_index_to_payload],
                                created_buffer.payload)


    @foreach(_test_generate_suppressed_events_for_source_data)
    def test_generate_suppressed_events_for_source(self, new_message, expected_results):
        """
        Check, if "suppressed" events are generated when a newly
        processed message's time is greater than its group's `until`
        time by the specified timeout (12 hours by default), or
        the message is from another day.
        """
        tested_source_data = self._get_source_data_for_suppressed_events_tests(
            self.tested_source_channel)
        another_source_data = self._get_source_data_for_suppressed_events_tests(
            self.other_source_channel)
        hifreq_new_data = HiFreqEventData(new_message)
        tested_source_data.groups["group1"] = hifreq_new_data
        # `time` attribute should be equal to last message's
        tested_source_data.time = datetime.datetime.strptime(
            new_message["time"], "%Y-%m-%d %H:%M:%S")
        another_source_data.time = datetime.datetime(2017, 6, 1, 10)
        # `last_event` attribute is not relevant for the test
        tested_source_data.last_event = datetime.datetime(2017, 6, 2, 20)
        another_source_data.last_event = datetime.datetime(2017, 6, 2, 20)
        self._adw.aggr_data.sources[self.tested_source_channel] = tested_source_data
        self._adw.aggr_data.sources[self.other_source_channel] = another_source_data

        generated_events = list(self._adw.generate_suppresed_events_for_source(new_message))
        self.assertItemsEqual(expected_results, generated_events)
        # new `HiFreqEventData` object of the "group1" should be
        # in `groups` attribute, but not in `buffer` - suppressed
        # event of the "group1" should have been generated
        self.assertIn(
            "group1", self._adw.aggr_data.sources[self.tested_source_channel].groups)
        self.assertNotIn(
            "group1", self._adw.aggr_data.sources[self.tested_source_channel].buffer)
        # if aggregated events of the "group2" were generated, then
        # there should not be any `HiFreqEventData` objects of this
        # group in `groups` nor `buffer` attribute
        if self.group2_expected_suppressed_event in expected_results:
            self.assertNotIn(
                "group2", self._adw.aggr_data.sources[self.tested_source_channel].groups)
            self.assertNotIn(
                "group2", self._adw.aggr_data.sources[self.tested_source_channel].buffer)

        # check if the other source's elements, for which suppressed
        # events were not generated, are unchanged
        self.assertIn(
            "group2", self._adw.aggr_data.sources[self.other_source_channel].groups)
        self.assertIn(
            "group1", self._adw.aggr_data.sources[self.other_source_channel].buffer)


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
            self.tested_source_channel)
        another_source_data = self._get_source_data_for_suppressed_events_tests(
            self.other_source_channel)
        # `time` attribute should be equal to last message's
        tested_source_data.time = datetime.datetime(2017, 6, 1, 10)
        another_source_data.time = datetime.datetime(2017, 6, 1, 10)
        tested_source_data.last_event = datetime.datetime(2017, 6, 1, 14)
        another_source_data.last_event = datetime.datetime(2017, 6, 1, 20)
        self._adw.aggr_data.sources[self.tested_source_channel] = tested_source_data
        self._adw.aggr_data.sources[self.other_source_channel] = another_source_data

        source_to_expected_events = self._get_source_to_expected_events_mapping()

        with patch("n6.utils.aggregator.datetime") as datetime_mock:
            datetime_mock.datetime.utcnow.return_value = mocked_utcnow
            datetime_mock.datetime.side_effect = (lambda *args, **kw:
                                                  datetime.datetime(*args, **kw))
            # a `SourceData` attribute `time_tolerance` needs
            # a `datetime.timedelta` instance, but it is mocked now
            datetime_mock.timedelta.side_effect = (lambda *args, **kw:
                                                   datetime.timedelta(*args, **kw))
            # actual call
            generated_events = list(self._adw.generate_suppresed_events_after_timeout())
            expected_events = [event for source, vals in source_to_expected_events.iteritems()
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

        group1_hifreq_buffered_data = HiFreqEventData.__new__(HiFreqEventData)
        group1_hifreq_buffered_data.payload = {
            "id": "c4ca4238a0b923820dcc509a6f75849b",
            "source": source_name,
            "_group": "group1",
            "time": "2017-06-01 07:00:00",
        }
        group1_hifreq_buffered_data.first = datetime.datetime(2017, 6, 1, 7)
        group1_hifreq_buffered_data.until = datetime.datetime(2017, 6, 1, 9)
        group1_hifreq_buffered_data.count = 5
        source_data.buffer["group1"] = group1_hifreq_buffered_data

        group2_hifreq_data = HiFreqEventData.__new__(HiFreqEventData)
        group2_hifreq_data.payload = {
            "id": "c4ca4238a0b923820dcc509a6f75849c",
            "source": source_name,
            "_group": "group2",
            "time": "2017-06-01 08:00:00",
        }
        group2_hifreq_data.until = datetime.datetime(2017, 6, 1, 10)
        group2_hifreq_data.first = datetime.datetime(2017, 6, 1, 8)
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
        group1_other_source_payload["source"] = self.other_source_channel
        group1_other_source_event = ("suppressed", group1_other_source_payload)
        group2_other_source_payload = self.group2_expected_suppressed_payload.copy()
        group2_other_source_payload["source"] = self.other_source_channel
        group2_other_source_event = ("suppressed", group2_other_source_payload)
        group3_other_source_event = self.group3_expected_suppressed_event
        return {
            self.tested_source_channel: [
                self.group1_expected_suppressed_event,
                self.group2_expected_suppressed_event,
                self.group3_expected_suppressed_event,
            ],
            self.other_source_channel: [
                group1_other_source_event,
                group2_other_source_event,
                group3_other_source_event,
            ],
        }

    def _get_time_tolerance_from_source(self, source):
        return self.sample_time_tolerance_per_source.get(source) or self.sample_time_tolerance


class TestAggregatorData(unittest.TestCase):

    sample_source = "testsource.testchannel"
    sample_other_source = "othersource.otherchannel"
    sample_group = "group1"
    sample_other_group = "group2"
    sample_time_tolerance = 500
    sample_time_tolerance_per_source = {
        sample_other_source: 1000,
    }

    groups_hifreq_data = HiFreqEventData(
        {
            "id": "c4ca4238a0b923820dcc509a6f75849c",
            "source": sample_source,
            "_group": sample_group,
            "time": "2017-06-02 12:00:00",
        }
    )
    buffer_hifreq_data = HiFreqEventData(
        {
            "id": "c4ca4238a0b923820dcc509a6f75849b",
            "source": sample_source,
            "_group": sample_group,
            "time": "2017-06-01 10:00:00",
        }
    )

    def setUp(self):
        self._aggregator_data = AggregatorData()
        self._sample_source_data = SourceData(self.sample_time_tolerance)
        self._sample_source_data.time = datetime.datetime(2017, 6, 2, 12)
        self._sample_source_data.last_event = datetime.datetime(2017, 6, 2, 13)
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
        self.assertEqual(source_data.last_event, None)
        self.assertFalse(source_data.groups)
        self.assertFalse(source_data.buffer)
        self.assertEqual(
            source_data.time_tolerance,
            datetime.timedelta(seconds=self._get_time_tolerance_from_source(
                self.sample_other_source)))
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
        self.assertEqual(source_data.last_event, self._sample_source_data.last_event)
        self.assertEqual(
            source_data.time_tolerance,
            datetime.timedelta(seconds=self._get_time_tolerance_from_source(self.sample_source)))
        self.assertIn(self.sample_group, source_data.groups)
        self.assertIn(self.sample_group, source_data.buffer)
        self.assertEqual(1, len(source_data.groups))
        self.assertEqual(1, len(source_data.buffer))
        self.assertEqual(self.groups_hifreq_data, source_data.groups[self.sample_group])
        self.assertEqual(self.buffer_hifreq_data, source_data.buffer[self.sample_group])
        self.assertIs(source_data, self._aggregator_data.sources[self.sample_source])

    def _get_time_tolerance_from_source(self, source):
        return self.sample_time_tolerance_per_source.get(source) or self.sample_time_tolerance

# Copyright (c) 2017-2023 NASK. All rights reserved.

import contextlib
import copy
import datetime
import inspect
import json
import re
import unittest
from collections.abc import (
    Callable,
    Generator,
    Sequence,
)
from unittest.mock import (
    AsyncMock,
    Mock,
    call,
    sentinel,
)
from urllib.parse import urlsplit

import requests
from dateutil.tz import gettz
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.misp import (
    MispCollector,
    SampleDownloadFailure,
    LOGGER as module_logger,
)
from n6datasources.tests.collectors._collector_test_helpers import BaseCollectorTestCase
from n6lib.common_helpers import PlainNamespace
from n6lib.config import ConfigError
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
    JSONWhoseContentIsEqualTo,
    TestCaseMixin,
)


#
# Test data + related helpers
#

# * Constants:

CONFIG_CONTENT = '''
    [example_misp_collector_config]

    # The 1st segment of the source identifier (the 2nd is always `misp`).
    source_provider = test

    misp_url = https://example.com
    misp_key = Example-Auth-Key
    days_for_first_run = 20

    ;minimum_tlp...

    sample_path = /exampleUrlPath/download/
    download_retries = 4
    max_acceptable_days_of_continuous_download_failures = 20
'''

MOCKED_NOW_DATETIME = datetime.datetime(year=2017, month=2, day=20, hour=12)

RAW_MISP_EVENTS = (
    '{"response": [{"Event": {"orgc_id": "1", "ShadowAttribute": [], "id": '
    '"560", "threat_level_id": "1", "uuid": "5895ceec-1a20-4188-a1f3-1b40c0'
    'a83832", "Orgc": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a83832", "id"'
    ': "1", "name": "MISP"}, "Org": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c'
    '0a83832", "id": "1", "name": "MISP"}, "RelatedEvent": [], "sharing_gro'
    'up_id": "0", "timestamp": "1486219333", "date": "2017-02-10", "disable'
    '_correlation": false, "info": "Event drugi", "locked": false, "publish'
    '_timestamp": "1486219345", "Attribute": [{"category": "Artifacts dropp'
    'ed", "comment": "", "uuid": "5895ceff-db34-4efb-9435-1b3fc0a83832", "e'
    'vent_id": "560", "timestamp": "1486212863", "to_ids": true, "deleted":'
    ' false, "value": "syslog.png|14ed4644f44ac852ba5d4b3b3ac6126e317e9acc"'
    ', "sharing_group_id": "0", "ShadowAttribute": [], "disable_correlation'
    '": false, "SharingGroup": [], "distribution": "5", "type": "filename|s'
    'ha1", "id": "144657"}, {"category": "Artifacts dropped", "comment": ""'
    ', "uuid": "5895cf0f-cfec-4487-b2a9-4836c0a83832", "event_id": "560", "'
    'timestamp": "1486212879", "to_ids": true, "deleted": false, "value": "'
    'sample_n6_properties|9dbc8de342551aa62eac4c5b0ac42d0d39148939", "shari'
    'ng_group_id": "0", "ShadowAttribute": [], "disable_correlation": false'
    ', "SharingGroup": [], "distribution": "5", "type": "filename|sha1", "i'
    'd": "144660"}, {"category": "Artifacts dropped", "comment": "", "uuid"'
    ': "5895cf24-e7ac-4427-8602-2f89c0a83832", "event_id": "560", "timestam'
    'p": "1486212900", "to_ids": true, "deleted": false, "value": "kolska.o'
    'dt|2d50d4688e9d5e78bb8aecf448226ca1a525b96d", "sharing_group_id": "0",'
    ' "ShadowAttribute": [], "disable_correlation": false, "SharingGroup": '
    '[], "distribution": "5", "type": "filename|sha1", "id": "144663"}, {"c'
    'ategory": "Artifacts dropped", "comment": "", "uuid": "5895cf32-abb0-4'
    'e0d-aede-490fc0a83832", "event_id": "560", "timestamp": "1486212914", '
    '"to_ids": true, "deleted": false, "value": "misp_sample|fb145a0fef0ca3'
    '788349a4ba1f26db1c0b88cc31", "sharing_group_id": "0", "ShadowAttribute'
    '": [], "disable_correlation": false, "SharingGroup": [], "distribution'
    '": "5", "type": "filename|sha1", "id": "144666"}, {"category": "Artifa'
    'cts dropped", "comment": "", "uuid": "5895ceff-357c-4952-a6ba-1b3fc0a8'
    '3832", "event_id": "560", "timestamp": "1486212863", "to_ids": true, "'
    'deleted": false, "value": "syslog.png|b22bfabfc6896f526a19dcfadbae9d3a'
    '5636972bab7bbeeb7489182d957a3063", "sharing_group_id": "0", "ShadowAtt'
    'ribute": [], "disable_correlation": false, "SharingGroup": [], "distri'
    'bution": "5", "type": "filename|sha256", "id": "144658"}, {"category":'
    ' "Artifacts dropped", "comment": "", "uuid": "5895cf0f-a158-40c1-b9de-'
    '4836c0a83832", "event_id": "560", "timestamp": "1486212879", "to_ids":'
    ' true, "deleted": false, "value": "sample_n6_properties|5878690a8f63b5'
    '6d0e444b94a5f8dec5d321f7ba25afc57951abc42560888ed9", "sharing_group_id'
    '": "0", "ShadowAttribute": [], "disable_correlation": false, "SharingG'
    'roup": [], "distribution": "5", "type": "filename|sha256", "id": "1446'
    '61"}, {"category": "Artifacts dropped", "comment": "", "uuid": "5895cf'
    '24-091c-4244-babe-2f89c0a83832", "event_id": "560", "timestamp": "1486'
    '212900", "to_ids": true, "deleted": false, "value": "kolska.odt|298eac'
    'b2c9684d012267b6055e861e316134d920ea8d49a3ade5697c93335b27", "sharing_'
    'group_id": "0", "ShadowAttribute": [], "disable_correlation": false, "'
    'SharingGroup": [], "distribution": "5", "type": "filename|sha256", "id'
    '": "144664"}, {"category": "Artifacts dropped", "comment": "", "uuid":'
    ' "5895cf32-7290-494e-826d-490fc0a83832", "event_id": "560", "timestamp'
    '": "1486212914", "to_ids": true, "deleted": false, "value": "misp_samp'
    'le|512d47b0ee0cb463598eb8376840216ed2866848300d5952b2e5efee311ee6bc", '
    '"sharing_group_id": "0", "ShadowAttribute": [], "disable_correlation":'
    ' false, "SharingGroup": [], "distribution": "5", "type": "filename|sha'
    '256", "id": "144667"}, {"category": "Artifacts dropped", "comment": ""'
    ', "uuid": "5895ceff-32f0-4c03-946b-1b3fc0a83832", "event_id": "560", "'
    'timestamp": "1486212863", "to_ids": true, "deleted": false, "value": "'
    'syslog.png|e2f88b5d31b03b319c36cfb4979e7f8e", "sharing_group_id": "0",'
    ' "ShadowAttribute": [], "disable_correlation": false, "SharingGroup": '
    '[], "distribution": "5", "type": "malware-sample", "id": "144656"}, {"'
    'category": "Artifacts dropped", "comment": "", "uuid": "5895cf0f-ebf4-'
    '4662-b9c8-4836c0a83832", "event_id": "560", "timestamp": "1486212879",'
    ' "to_ids": true, "deleted": false, "value": "sample_n6_properties|8644'
    '071ccfff945ecd6127300a932fbd", "sharing_group_id": "0", "ShadowAttribu'
    'te": [], "disable_correlation": false, "SharingGroup": [], "distributi'
    'on": "5", "type": "malware-sample", "id": "144659"}, {"category": "Art'
    'ifacts dropped", "comment": "", "uuid": "5895cf24-51e4-4868-9412-2f89c'
    '0a83832", "event_id": "560", "timestamp": "1486212900", "to_ids": true'
    ', "deleted": false, "value": "kolska.odt|6e98c9e4b0b2232d331fb80ea5f19'
    '7bc", "sharing_group_id": "0", "ShadowAttribute": [], "disable_correla'
    'tion": false, "SharingGroup": [], "distribution": "5", "type": "malwar'
    'e-sample", "id": "144662"}, {"category": "Artifacts dropped", "comment'
    '": "", "uuid": "5895cf32-b3e8-4a7d-865c-490fc0a83832", "event_id": "56'
    '0", "timestamp": "1486212914", "to_ids": true, "deleted": false, "valu'
    'e": "misp_sample|d6d88f2e50080b9602da53dac1102762", "sharing_group_id"'
    ': "0", "ShadowAttribute": [], "disable_correlation": false, "SharingGr'
    'oup": [], "distribution": "5", "type": "malware-sample", "id": "144665'
    '"}], "attribute_count": "12", "org_id": "1", "analysis": "0", "publish'
    'ed": true, "distribution": "3", "proposal_email_lock": false, "Galaxy"'
    ': []}}, {"Event": {"orgc_id": "1", "ShadowAttribute": [], "id": "559",'
    ' "threat_level_id": "1", "uuid": "5895b819-37a0-4f2d-99fa-1abcc0a83832'
    '", "Orgc": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a83832", "id": "1",'
    ' "name": "MISP"}, "Org": {"uuid": "56ef3277-1ad4-42f6-b90b-04e5c0a8383'
    '2", "id": "1", "name": "MISP"}, "RelatedEvent": [], "sharing_group_id"'
    ': "0", "timestamp": "1486219299", "date": "2017-02-14", "disable_corre'
    'lation": false, "info": "Event numer jeden", "locked": false, "publish'
    '_timestamp": "1486219315", "Attribute": [{"category": "Artifacts dropp'
    'ed", "comment": "", "uuid": "5895b83d-29a4-4a3b-bc01-1b40c0a83832", "e'
    'vent_id": "559", "timestamp": "1486207037", "to_ids": true, "deleted":'
    ' false, "value": "wniosek.pdf|3d95be6f118dfabe73f4a1c7c77a7d0d2f9ef6a8'
    '59c61845d5e667bc10f1017f", "sharing_group_id": "0", "ShadowAttribute":'
    ' [], "disable_correlation": false, "SharingGroup": [], "distribution":'
    ' "5", "type": "filename|sha256", "id": "144648"}, {"category": "Artifa'
    'cts dropped", "comment": "", "uuid": "5895b855-a930-4b6c-b399-2f88c0a8'
    '3832", "event_id": "559", "timestamp": "1486207061", "to_ids": true, "'
    'deleted": false, "value": "zone_h_par.py|9ea826ef6f2761e11069ffa045c81'
    'a7235ebea9f59c27228594837fcc6ebdeb4", "sharing_group_id": "0", "Shadow'
    'Attribute": [], "disable_correlation": false, "SharingGroup": [], "dis'
    'tribution": "5", "type": "filename|sha256", "id": "144651"}, {"categor'
    'y": "Artifacts dropped", "comment": "", "uuid": "5895b87e-5ca0-4510-96'
    '1f-2f88c0a83832", "event_id": "559", "timestamp": "1486207102", "to_id'
    's": true, "deleted": false, "value": "wsdl|c61abf92233ee033474e8d91454'
    'fe10a3cce1325af42266a68df124d41dd44d0", "sharing_group_id": "0", "Shad'
    'owAttribute": [], "disable_correlation": false, "SharingGroup": [], "d'
    'istribution": "5", "type": "filename|sha256", "id": "144655"}, {"categ'
    'ory": "Artifacts dropped", "comment": "", "uuid": "5895b83d-cf34-4c9f-'
    'a921-1b40c0a83832", "event_id": "559", "timestamp": "1486207037", "to_'
    'ids": true, "deleted": false, "value": "wniosek.pdf|f0dc87b83bc6953c88'
    '44eafa55a256bf", "sharing_group_id": "0", "ShadowAttribute": [], "disa'
    'ble_correlation": false, "SharingGroup": [], "distribution": "5", "typ'
    'e": "malware-sample", "id": "1"}, {"category": "Artifacts dropped'
    '", "comment": "", "uuid": "5895b855-eed0-4f1a-8184-2f88c0a83832", "eve'
    'nt_id": "559", "timestamp": "1486207061", "to_ids": true, "deleted": f'
    'alse, "value": "zone_h_par.py|cc5fc5eff65fb15f66d43f7d0dc90328", "shar'
    'ing_group_id": "0", "ShadowAttribute": [], "disable_correlation": fals'
    'e, "SharingGroup": [], "distribution": "5", "type": "malware-sample", '
    '"id": "2"}, {"category": "Artifacts dropped", "comment": "", "uui'
    'd": "5895b87e-8f18-4d8c-956f-2f88c0a83832", "event_id": "559", "timest'
    'amp": "1486207102", "to_ids": true, "deleted": false, "value": "wsdl|7'
    '2fdafceec16ce8e75d3fb1b0174ba06", "sharing_group_id": "0", "ShadowAttr'
    'ibute": [], "disable_correlation": false, "SharingGroup": [], "distrib'
    'ution": "5", "type": "malware-sample", "id": "144653"}], "attribute_co'
    'unt": "6", "org_id": "1", "analysis": "0", "published": true, "distrib'
    'ution": "3", "proposal_email_lock": false, "Galaxy": []}}]}')

ALL_EVENTS = EVENT_2017_02_10, EVENT_2017_02_14 = json.loads(RAW_MISP_EVENTS)['response']

SAMPLES_2017_02_10 = {
    144656: b'Event nr 144656 binary data.',
    144659: b'Event nr 144659 binary data.',
    144662: b'Event nr 144662 binary data.',
    144665: b'Event nr 144665 binary data.',
}
SAMPLES_2017_02_14 = {
    1: b'Event nr 1 binary data.',
    2: b'Event nr 2 binary data.',
    144653: b'Event nr 144653 binary data.',
}
ALL_SAMPLES = SAMPLES_2017_02_10 | SAMPLES_2017_02_14


# * Test case parameters:

@paramseq
def whole_collector_run_test_cases():
    all_events = list(ALL_EVENTS)
    all_sample_ids = list(ALL_SAMPLES.keys())

    older_sample_ids = list(SAMPLES_2017_02_10.keys())

    newer_events = [EVENT_2017_02_14]
    newer_sample_ids = list(SAMPLES_2017_02_14.keys())

    typical_expected_saved_state = {
        'events_last_proc_datetime': MOCKED_NOW_DATETIME,
        'samples_last_proc_datetime': MOCKED_NOW_DATETIME,
        'already_processed_sample_ids': set(),
    }

    get_expected_recorded_calls = _get_expected_recorded_calls_for_whole_collector_run

    for configured_minimum_tlp in [None, '', 'white', 'GREEN', 'Amber', 'reD']:
        if configured_minimum_tlp is None:
            config_content = CONFIG_CONTENT
            configured_minimum_tlp_repr = '<default empty>'
        else:
            config_content = CONFIG_CONTENT.replace(
                ';minimum_tlp...',
                f'minimum_tlp = {configured_minimum_tlp}')
            configured_minimum_tlp_repr = (
                repr(configured_minimum_tlp) if configured_minimum_tlp
                else '<explicit empty>')
        label_prefix = f'[minimum_tlp={configured_minimum_tlp_repr}] '

        yield param(
            config_content,
            initial_state=sentinel.NO_STATE,
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='28815m',  # (here `days_for_first_run` matters)
                expected_events=all_events,
                expected_sample_ids=all_sample_ids,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'All events and samples, no previous state.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=all_sample_ids,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'All events and samples, with initial state.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            sample_exchange_declared=False,
            expected_exc_class=SystemExit,
            expected_exc_regex=(
                r"RuntimeError.*"
                r"exchange 'sample' is not declared, "
                r"so no samples could be processed"),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=None,
            ),
            expected_warn_regexes=[
                r"WARNING.*"
                r"Exchange 'sample' is not declared! Any malware "
                r"samples that could be processed and published "
                r"will \*not\* be processed/published yet ",
            ],
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': set(),
            },
        ).label(label_prefix +
        'Undeclared `sample` exchange => fatal error.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            failed_download_sample_ids=frozenset({144659, 2}),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset({144659, 2}),
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=all_sample_ids,
            ),
            expected_warn_regexes=[
                r'WARNING.*Cannot download the sample whose id is 144659 ',
                r'WARNING.*Cannot download the sample whose id is 2 ',
                r'WARNING.*Out of 7 sample downloads.* 5 were successful and 2 were \*not\*'
            ],
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'All events, yet some samples cannot be downloaded.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            failed_download_sample_ids=frozenset(all_sample_ids),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset(all_sample_ids),
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=all_sample_ids,
            ),
            expected_warn_regexes=[
                rf'WARNING.*Cannot download the sample whose id is {sample_id} '
                for sample_id in all_sample_ids
            ] + [
                r'WARNING.*Attempted to download 7 samples.* but \*all\* those downloads failed',
            ],
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': set(),
            },
        ).label(label_prefix +
        'All events, yet no samples can be downloaded at all.')

        yield param(
            config_content.replace(
                'max_acceptable_days_of_continuous_download_failures = 20',
                'max_acceptable_days_of_continuous_download_failures = 10'),
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            failed_download_sample_ids=frozenset(all_sample_ids),
            expected_exc_class=SystemExit,
            expected_exc_regex=(
                r'RuntimeError.*'
                r'continuous sample download failures have been '
                r'being observed for samples from more than 10 days'),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset(all_sample_ids),
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=all_sample_ids,
            ),
            expected_warn_regexes=[
                rf'WARNING.*Cannot download the sample whose id is {sample_id} '
                for sample_id in all_sample_ids
            ] + [
                r'WARNING.*Attempted to download 7 samples.* but \*all\* those downloads failed',
            ],
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': set(),
            },
        ).label(label_prefix +
        'All events, yet no samples can be downloaded at all '
        '+ exceeding `max_acceptable_days_of_continuous_download_failures` => fatal error.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'already_processed_sample_ids': set(),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='7215m',
                expected_events=None,
                expected_sample_ids=None,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'No new events and no overdue samples.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 12, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='11535m',
                expected_events=newer_events,
                expected_misp_2nd_search_arg_last='15855m',
                expected_sample_ids=all_sample_ids,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'Events after 2017-02-12 and overdue samples.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 12, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            failed_download_sample_ids=frozenset(all_sample_ids),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset(all_sample_ids),
                expected_misp_search_arg_last='11535m',
                expected_events=newer_events,
                expected_misp_2nd_search_arg_last='15855m',
                expected_sample_ids=all_sample_ids,
            ),
            expected_warn_regexes=[
                rf'WARNING.*Cannot download the sample whose id is {sample_id} '
                for sample_id in all_sample_ids
            ] + [
                r'WARNING.*Attempted to download 7 samples.* but \*all\* those downloads failed',
            ],
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': set(),
            },
        ).label(label_prefix +
        'Events after 2017-02-12 and overdue samples, yet no samples can be downloaded at all.')

        yield param(
            config_content.replace(
                'max_acceptable_days_of_continuous_download_failures = 20',
                # (let the default value, which is 3, be used)
                ''),
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 12, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            failed_download_sample_ids=frozenset(all_sample_ids),
            expected_exc_class=SystemExit,
            expected_exc_regex=(
                r'RuntimeError.*'
                r'continuous sample download failures have been '
                r'being observed for samples from more than 3 days'),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset(all_sample_ids),
                expected_misp_search_arg_last='11535m',
                expected_events=newer_events,
                expected_misp_2nd_search_arg_last='15855m',
                expected_sample_ids=all_sample_ids,
            ),
            expected_warn_regexes=[
                rf'WARNING.*Cannot download the sample whose id is {sample_id} '
                for sample_id in all_sample_ids
            ] + [
                r'WARNING.*Attempted to download 7 samples.* but \*all\* those downloads failed',
            ],
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': set(),
            },
        ).label(label_prefix +
        'Events after 2017-02-12 and overdue samples, yet no samples can be downloaded at all '
        '+ exceeding `max_acceptable_days_of_continuous_download_failures` => fatal error.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='7215m',
                expected_events=None,
                expected_misp_2nd_search_arg_last='15855m',
                expected_sample_ids=all_sample_ids,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'No new events, overdue samples after 2017-02-09.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 12, 12),
                'already_processed_sample_ids': set(),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='7215m',
                expected_events=None,
                expected_misp_2nd_search_arg_last='11535m',
                expected_sample_ids=newer_sample_ids,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'No new events, overdue samples after 2017-02-12.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 12, 12),
                'already_processed_sample_ids': set(),
            },
            failed_download_sample_ids=frozenset({1, 2}),
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset({1, 2}),
                expected_misp_search_arg_last='7215m',
                expected_events=None,
                expected_misp_2nd_search_arg_last='11535m',
                expected_sample_ids=newer_sample_ids,
            ),
            expected_warn_regexes=[
                r'WARNING.*Cannot download the sample whose id is 1 ',
                r'WARNING.*Cannot download the sample whose id is 2 ',
                r'WARNING.*Out of 3 sample downloads.* 1 were successful and 2 were \*not\*'
            ],
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'No new events, overdue samples after 2017-02-12, some of which cannot be downloaded')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 11, 12),
                'already_processed_sample_ids': {1, 144653},
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='7215m',
                expected_events=None,
                expected_misp_2nd_search_arg_last='12975m',
                expected_sample_ids=[
                    sample_id for sample_id in newer_sample_ids
                    if sample_id not in {1, 144653}],
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'No new events, overdue samples after 2017-02-11, partially downloaded.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 11, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': {144656, 144659},
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='12975m',
                expected_events=newer_events,
                expected_misp_2nd_search_arg_last='15855m',
                expected_sample_ids=[
                    sample_id for sample_id in all_sample_ids
                    if sample_id not in {144656, 144659}]
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'Events after 2017-02-11, overdue samples after 2017-02-09, partially downloaded.')

        # * Less probable (yet still properly handled) cases:

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 15, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 11, 12),
                'already_processed_sample_ids': set(all_sample_ids),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='7215m',
                expected_events=None,
                expected_misp_2nd_search_arg_last='12975m',
                expected_sample_ids=None,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'No new events, overdue samples after 2017-02-11, all already downloaded.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 11, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(all_sample_ids),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='12975m',
                expected_events=newer_events,
                expected_misp_2nd_search_arg_last='15855m',
                expected_sample_ids=None,
            ),
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'Events after 2017-02-11, overdue samples after 2017-02-09, all already downloaded.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 18, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 17, 12),
                'already_processed_sample_ids': set(),
            },
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                expected_misp_search_arg_last='2895m',
                expected_events=None,
                expected_misp_2nd_search_arg_last='4335m',
                expected_sample_ids=None,
            ),
            expected_warn_regexes=[
                r'WARNING.*The loaded state indicates that there should '
                r'be overdue samples to publish, since 2017-02-17 12:00:00\. '
                r'However, according to the queried MISP system, there are '
                r'no events and no associated malware samples to download '
                r'for that period\.',
            ],
            expected_saved_state=typical_expected_saved_state,
        ).label(label_prefix +
        'Overdue samples expected according to state, but then it appears there are no samples.')

        # * Breaking exceptions

        *preceding_sample_ids, exc_triggering_sample_id = older_sample_ids
        expected_success_proc_sample_ids = set(preceding_sample_ids)
        assert (exc_triggering_sample_id == 144665
                and expected_success_proc_sample_ids == {144656, 144659, 144662})

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            sample_id_whose_download_causes_breaking_exc=exc_triggering_sample_id,
            breaking_exc=KeyboardInterrupt,
            expected_exc_class=KeyboardInterrupt,
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset({exc_triggering_sample_id}),
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=older_sample_ids,
            ),
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': expected_success_proc_sample_ids,  # (<- non-empty)
            },
        ).label(label_prefix +
        'KeyboardInterrupt exception.')

        yield param(
            config_content,
            initial_state={
                'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
                'already_processed_sample_ids': set(),
            },
            sample_id_whose_download_causes_breaking_exc=exc_triggering_sample_id,
            breaking_exc=ZeroDivisionError('arbitrary error example'),
            expected_exc_class=SystemExit,
            expected_exc_regex=r'ZeroDivisionError.*arbitrary error example',
            expected_recorded_calls=get_expected_recorded_calls(
                configured_minimum_tlp,
                failed_download_sample_ids=frozenset({exc_triggering_sample_id}),
                expected_misp_search_arg_last='15855m',
                expected_events=all_events,
                expected_sample_ids=older_sample_ids,
            ),
            expected_saved_state={
                'events_last_proc_datetime': MOCKED_NOW_DATETIME,
                'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),  # (<- unchanged)
                'already_processed_sample_ids': expected_success_proc_sample_ids,  # (<- non-empty)
            },
        ).label(label_prefix +
        'Arbitrary fatal error.')


@paramseq
def wrong_state_test_cases():
    yield param(
        state=[
            ('events_last_proc_datetime', datetime.datetime(2017, 2, 9, 12)),
            ('samples_last_proc_datetime', datetime.datetime(2017, 2, 9, 12)),
            ('already_processed_sample_ids', set()),
        ],
        expected_exc_class=TypeError,
        expected_exc_regex=r'encountered a wrong state: not a dict ',
    ).label('Not a dict.')

    yield param(
        state={
            'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'already_processed_sample_ids': set(),
        },
        expected_exc_class=ValueError,
        expected_exc_regex=r'encountered a wrong state: its keys should be ',
    ).label('Missing key.')

    yield param(
        state={
            'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'some_illegal_key': datetime.datetime(2017, 2, 9, 12),
            'already_processed_sample_ids': set(),
        },
        expected_exc_class=ValueError,
        expected_exc_regex=r'encountered a wrong state: its keys should be ',
    ).label('Illegal key.')

    yield param(
        state={
            'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'samples_last_proc_datetime': datetime.datetime(2017, 2, 12, 12),
            'already_processed_sample_ids': set(),
        },
        expected_exc_class=ValueError,
        expected_exc_regex=(
            r'encountered a wrong state: the last sample publication '
            r'datetime should be the same as or earlier than the last '
            r'event publication datetime'),
    ).label('Last sample publication date+time later than last event publication date+time.')


@paramseq
def download_sample_test_cases():

    def response(status_code):
        return PlainNamespace(status_code=status_code)

    retryable_error_response = response(500)
    non_retryable_error_response = response(404)

    expected_download_call = call.download(
        sentinel.url,
        retries=0,
        custom_request_headers={
            'Authorization': 'Example-Auth-Key',
        },
    )

    yield param(
        expected_sample_data_body=b'Result of download attempt #1',
        expected_recorded_calls=[
            call.pub_iter_yield(None),
            expected_download_call,
            call.LOGGER.info(
                'Downloaded a %d-bytes malware sample from %a.',
                29,
                sentinel.url,
            ),
        ],
    ).label('Immediate success.')

    yield param(
        download_error_factories=[
            lambda: requests.ConnectionError('Ni!'),
            lambda: requests.ConnectTimeout('Nu...'),
            lambda: requests.Timeout('ekke ekke ekke ekke ptang zoo boing'),
            lambda: requests.HTTPError("it can't be done", response=retryable_error_response),
        ],
        expected_sample_data_body=b'Result of download attempt #5',
        expected_recorded_calls=[
            call.pub_iter_yield(None),

            # Attempt #1 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                '[from sentinel.url] ConnectionError: Ni!',
                2,
            ),
            call.time.sleep(2),
            call.pub_iter_yield(None),

            # Attempt 2 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                ('[after 2 download attempts from sentinel.url] '
                 'ConnectTimeout: Nu...'),
                4,
            ),
            call.time.sleep(4),  # (twice as long as before)
            call.pub_iter_yield(None),

            # Attempt #3 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                ('[after 3 download attempts from sentinel.url] '
                 'Timeout: ekke ekke ekke ekke ptang zoo boing'),
                8,
            ),
            call.time.sleep(8),  # (again, twice as long as before...)
            call.pub_iter_yield(None),

            # Attempt #4 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                ("[after 4 download attempts from sentinel.url] "
                 "HTTPError: it can't be done"),
                10,
            ),
            call.time.sleep(10),  # (...but never longer than 10 seconds)
            call.pub_iter_yield(None),

            # Attempt #5 (successful):
            expected_download_call,
            call.LOGGER.info(
                'Downloaded a %d-bytes malware sample from %a.',
                29,
                sentinel.url,
            ),
        ],
    ).label('Success, albeit with a few problems along the way.')

    yield param(
        download_error_factories=[
            lambda: requests.HTTPError('Confess...', response=response(500)),
            lambda: requests.HTTPError('Confess!', response=response(502)),
            lambda: requests.HTTPError('Confess!!!', response=response(503)),
            lambda: requests.Timeout('I confess!'),
            lambda: requests.HTTPError('Not you!', response=response(504)),
        ],
        expected_exc_class=SampleDownloadFailure,
        expected_exc_regex=(
            r'^\[after 5 download attempts from sentinel\.url\] '
            r'HTTPError: Not you!$'),
        expected_recorded_calls=[
            call.pub_iter_yield(None),

            # Attempt #1 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                '[from sentinel.url] HTTPError: Confess...',
                2,
            ),
            call.time.sleep(2),
            call.pub_iter_yield(None),

            # Attempt 2 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                ('[after 2 download attempts from sentinel.url] '
                 'HTTPError: Confess!'),
                4,
            ),
            call.time.sleep(4),  # (twice as long as before)
            call.pub_iter_yield(None),

            # Attempt #3 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                ('[after 3 download attempts from sentinel.url] '
                 'HTTPError: Confess!!!'),
                8,
            ),
            call.time.sleep(8),  # (again, twice as long as before...)
            call.pub_iter_yield(None),

            # Attempt #4 (failed):
            expected_download_call,
            call.pub_iter_yield(None),
            call.LOGGER.info(
                ('A retryable error occurred while trying to download '
                 'a sample (%s). Retrying in %d seconds...'),
                ('[after 4 download attempts from sentinel.url] '
                 'Timeout: I confess!'),
                10,
            ),
            call.time.sleep(10),  # (...but never longer than 10 seconds)
            call.pub_iter_yield(None),

            # Attempt #5 (failed!):
            expected_download_call,
        ],
    ).label('Failure when exceeding `download_retries`.')

    yield param(
        download_error_factories=[
            lambda: requests.HTTPError("it can't be done", response=non_retryable_error_response),
        ],
        expected_exc_class=SampleDownloadFailure,
        expected_exc_regex=(
            r"^\[from sentinel\.url\] "
            r"HTTPError: it can't be done$"),
        expected_recorded_calls=[
            call.pub_iter_yield(None),
            expected_download_call,
        ],
    ).label('Immediate failure (HTTPError with non-retryable status code).')

    yield param(
        download_error_factories=[
            lambda: OSError('Nobody expects the Spanish Inquisition!'),
        ],
        expected_exc_class=SampleDownloadFailure,
        expected_exc_regex=(
            r'^\[from sentinel\.url\] '
            r'OSError: Nobody expects the Spanish Inquisition!$'),
        expected_recorded_calls=[
            call.pub_iter_yield(None),
            expected_download_call,
        ],
    ).label('Immediate failure (OSError).')

    yield param(
        download_error_factories=[
            lambda: ZeroDivisionError('arbitrary error example'),
        ],
        expected_exc_class=ZeroDivisionError,
        expected_exc_regex=r'^arbitrary error example$',
        expected_recorded_calls=[
            call.pub_iter_yield(None),
            expected_download_call,
        ],
    ).label('Arbitrary error.')


# * Case parametrization helpers:

def _get_expected_recorded_calls_for_whole_collector_run(
        configured_minimum_tlp,
        expected_events,
        expected_sample_ids,
        expected_misp_search_arg_last=None,
        expected_misp_2nd_search_arg_last=None,
        failed_download_sample_ids=frozenset()):

    expected_recorded_calls = []

    expected_recorded_calls.append(
        call._PyMISP_constructor(
            url='https://example.com',
            key='Example-Auth-Key',
            ssl=True,
        ),
    )

    if expected_misp_search_arg_last is not None:
        expected_recorded_calls.append(
            call._PyMISP_method__search(last=expected_misp_search_arg_last),
        )

    if expected_events:
        expected_recorded_calls.append(
            call.publish_output(
                # routing_key
                'test.misp',

                # body
                JSONWhoseContentIsEqualTo(expected_events),

                # prop_kwargs
                {
                    'timestamp': AnyInstanceOf(int),
                    'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
                    'type': 'stream',
                    'headers': (
                        {'meta': {'minimum_tlp': configured_minimum_tlp.lower()}}
                        if configured_minimum_tlp
                        else {}),
                },
            ),
        )

    if expected_misp_2nd_search_arg_last is not None:
        expected_recorded_calls.append(
            call._PyMISP_method__search(last=expected_misp_2nd_search_arg_last),
        )

    sample_id_to_metadata = _get_sample_id_to_metadata()
    for sample_id in (expected_sample_ids or []):
        sample_metadata = sample_id_to_metadata[sample_id]
        expected_recorded_calls.append(
            call._download_sample(
                f'https://example.com/exampleUrlPath/download/{sample_id}',
            ),
        )
        if sample_id in failed_download_sample_ids:
            continue
        expected_recorded_calls.append(
            call.publish_output(
                # routing_key
                'test.misp',

                # body
                ALL_SAMPLES[sample_id],

                # prop_kwargs
                {
                    'timestamp': AnyInstanceOf(int),
                    'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
                    'type': 'file',
                    'content_type': 'application/json',
                    'headers': {
                        'meta': {
                            'misp': {
                                k: sample_metadata[k] for k in [
                                    'category',
                                    'comment',
                                    'uuid',
                                    'event_id',
                                    'timestamp',
                                    'to_ids',
                                    'value',
                                    'distribution',
                                    'type',
                                    'id',
                                ] if k in sample_metadata
                            },
                        } | (
                            {'minimum_tlp': configured_minimum_tlp.lower()}
                            if configured_minimum_tlp
                            else {}),
                    },
                },

                exchange='sample',
            ),
        )

    return expected_recorded_calls


def _get_sample_id_to_metadata():
    sample_id_to_metadata = {}

    for ev in ALL_EVENTS:
        assert isinstance(ev, dict)
        assert isinstance(ev.get('Event'), dict)
        assert isinstance(ev['Event'].get('Attribute'), list)

        for misp_attribute_data in ev['Event']['Attribute']:
            assert isinstance(misp_attribute_data, dict)
            assert isinstance(misp_attribute_data.get('type'), str)
            assert isinstance(misp_attribute_data.get('id'), str)
            assert misp_attribute_data['id'].isdecimal()

            if misp_attribute_data['type'] == 'malware-sample':
                sample_id = int(misp_attribute_data['id'])
                # (copying in the spirit of *defensive programming*...)
                sample_id_to_metadata[sample_id] = misp_attribute_data.copy()

    return sample_id_to_metadata


#
# Actual implementation of tests
#

@expand
class TestMispCollector(BaseCollectorTestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Note ad the attribute `self.rec` and the test parameter
        # `expected_recorded_calls`: in these tests we record
        # invocations of a few collector methods as well as of
        # some other callables...
        self.rec = Mock()
        self.rec.publish_output = self.publish_output_mock


    # * Patching external stuff:

    def do_patching(self, **kwargs):
        super().do_patching(**kwargs)
        self.rec.attach_mock(
            self.patch('pymisp.PyMISP.__init__', return_value=None),
            '_PyMISP_constructor')
        self.rec.attach_mock(
            self.patch('pymisp.PyMISP.search', side_effect=self._PyMISP_search_side_effect),
            '_PyMISP_method__search')
        datetime_mock = self.patch('n6datasources.collectors.misp.datetime')
        datetime_mock.side_effect = datetime.datetime
        datetime_mock.utcnow.return_value = MOCKED_NOW_DATETIME

    def _PyMISP_search_side_effect(self, *, last):
        last_delta = datetime.timedelta(minutes=int(last.replace('m', '')))
        last_dt = MOCKED_NOW_DATETIME - last_delta
        raw_events = json.loads(RAW_MISP_EVENTS)['response']
        datetime_format = '%Y-%m-%d'
        events = [
            x['Event'] for x in raw_events
            if (datetime.datetime.strptime(x['Event']['date'], datetime_format) > last_dt)]
        result = {'response': [{'Event': x} for x in events]}
        return result


    # * Preparing collector instance:

    def get_prepared_collector(self,
                               config_content=CONFIG_CONTENT,
                               initial_state=sentinel.NO_STATE,
                               sample_exchange_declared=True,
                               download_sample_side_effect=None):
        collector = self.prepare_collector(
            MispCollector,
            config_content=config_content,
            cmdline_args=['example_misp_collector_config'],
            initial_state=initial_state)
        collector._declared_output_exchanges = (
            {'raw', 'sample'} if sample_exchange_declared
            else {'raw'})
        self.rec._download_sample = collector._download_sample = AsyncMock()
        if download_sample_side_effect is not None:
            collector._download_sample.side_effect = download_sample_side_effect
        return collector


    # * Actual tests:

    @foreach(whole_collector_run_test_cases)
    def test_whole_collector_run(self,
                                 config_content,
                                 initial_state,
                                 expected_recorded_calls,
                                 expected_saved_state,
                                 expected_warn_regexes=(),
                                 expected_exc_class=None,
                                 expected_exc_regex=r'.*',
                                 sample_exchange_declared=True,
                                 failed_download_sample_ids=frozenset(),
                                 sample_id_whose_download_causes_breaking_exc=None,
                                 breaking_exc=None):
        download_sample_side_effect = self._make_download_sample_side_effect(
            failed_download_sample_ids,
            sample_id_whose_download_causes_breaking_exc,
            breaking_exc)
        collector = self.get_prepared_collector(
            config_content,
            initial_state,
            sample_exchange_declared,
            download_sample_side_effect)
        exc_context = (
            contextlib.nullcontext() if expected_exc_class is None
            else self.assertRaisesRegex(expected_exc_class, expected_exc_regex))
        with exc_context, self.assertLogWarningRegexes(module_logger, expected_warn_regexes):

            collector.run_collection()

        assert self.rec.mock_calls == expected_recorded_calls
        assert self.saved_state == expected_saved_state

    def _make_download_sample_side_effect(self,
                                          failed_download_sample_ids,
                                          sample_id_whose_download_causes_breaking_exc=None,
                                          breaking_exc=None):
        async def _download_sample(url):
            split_url = urlsplit(url)
            sample_id = int(split_url.path.split('/')[-1])
            if sample_id == sample_id_whose_download_causes_breaking_exc:
                raise breaking_exc
            if sample_id in failed_download_sample_ids:
                raise SampleDownloadFailure('whatever')
            return ALL_SAMPLES[sample_id]
        return _download_sample


    @foreach('ni', 'BlackKnightAlwaysTriumphs', 'What... is your favorite color?', 'Blue! No, Yel')
    def test_wrong_config_option_minium_tlp_causes_error(self, configured_minimum_tlp):
        config_content = CONFIG_CONTENT.replace(
            ';minimum_tlp...',
            f'minimum_tlp = {configured_minimum_tlp}')

        with self.assertRaisesRegex(ConfigError, (rf"example_misp_collector_config\.minimum_tlp"
                                                  rf"='{re.escape(configured_minimum_tlp)}'")):
            self.prepare_collector(
                MispCollector,
                config_content=config_content,
                cmdline_args=['example_misp_collector_config'])


    @foreach(wrong_state_test_cases)
    def test_wrong_state_causes_error(self, state, expected_exc_class, expected_exc_regex):
        collector = self.get_prepared_collector(initial_state=state)

        with self.assertRaisesRegex(expected_exc_class, expected_exc_regex):
            collector.run_collection()

        assert self.saved_state is sentinel.NO_STATE


    @foreach(download_sample_test_cases)
    def test__download_sample(self,
                              download_error_factories=(),
                              expected_sample_data_body=sentinel.NOT_OBTAINED,
                              *,
                              expected_recorded_calls,
                              expected_exc_class=None,
                              expected_exc_regex=None):
        collector = self.prepare_collector(
            MispCollector,
            config_content=CONFIG_CONTENT,
            cmdline_args=['example_misp_collector_config'])
        self.rec.attach_mock(self.patch('n6datasources.collectors.misp.time'), 'time')
        self.rec.attach_mock(self.patch('n6datasources.collectors.misp.LOGGER'), 'LOGGER')
        self.rec.attach_mock(
            self.patch(
                'n6datasources.collectors.base.BaseDownloadingCollector.download',
                side_effect=self._make_download_side_effect(download_error_factories)),
            'download')
        self.obtained_sample_data_body = sentinel.NOT_OBTAINED
        collector._http_last_modified = sentinel.NOT_TOUCHED
        assert collector.http_last_modified is sentinel.NOT_TOUCHED, 'test code expectation'

        coro = collector._download_sample(sentinel.url)
        gen = coro.__await__()
        if expected_exc_class is None:
            assert expected_exc_regex is None, 'test code expectation'
            assert expected_sample_data_body is not sentinel.NOT_OBTAINED, 'test code expectation'
            for yielded in self._run_downloading_gen(gen):
                self.rec.pub_iter_yield(yielded)
        else:
            assert expected_exc_regex is not None, 'test code expectation'
            assert expected_sample_data_body is sentinel.NOT_OBTAINED, 'test code expectation'
            with self.assertRaisesRegex(expected_exc_class, expected_exc_regex):
                for yielded in self._run_downloading_gen(gen):
                    self.rec.pub_iter_yield(yielded)

        assert self.obtained_sample_data_body == expected_sample_data_body
        assert self.rec.mock_calls == expected_recorded_calls
        assert inspect.iscoroutine(coro)
        assert collector.http_last_modified is None

    def _make_download_side_effect(self, download_error_factories: Sequence) -> Callable:
        attempt_count = 0

        def download(*_args, **_kw):
            nonlocal attempt_count
            attempt_count += 1

            if len(download_error_factories) >= attempt_count:
                error_factory = download_error_factories[attempt_count - 1]
                raise error_factory()

            return b'Result of download attempt #%d' % attempt_count

        return download

    def _run_downloading_gen(self, gen: Generator) -> Generator:
        assert isinstance(gen, Generator)
        self.obtained_sample_data_body = (yield from gen)


    def test__do_publish_events(self):
        output_components = ('test.misp', b'test body', sentinel.prop_kwargs)
        collector = self.get_prepared_collector()
        collector._now = MOCKED_NOW_DATETIME
        collector._state = {
            'events_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'already_processed_sample_ids': set(),
        }
        self.rec.attach_mock(self.patch('n6datasources.collectors.misp.LOGGER'), 'LOGGER')

        coro = collector._do_publish_events(output_components)
        yielded = list(coro.__await__())

        assert self.rec.mock_calls == [
            call.publish_output(*output_components),
            call.LOGGER.info('Published the event(s).'),
        ]
        assert inspect.iscoroutine(coro)
        assert yielded == ['FLUSH_OUT']
        assert self.saved_state == {
            'events_last_proc_datetime': MOCKED_NOW_DATETIME,
            'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'already_processed_sample_ids': set(),
        }


    def test__do_publish_sample(self):
        output_components = ('test.misp', b'test body', sentinel.prop_kwargs)
        pub_sample_metadata = {'id': 314159}
        collector = self.get_prepared_collector()
        collector._now = MOCKED_NOW_DATETIME
        collector._state = {
            'events_last_proc_datetime': MOCKED_NOW_DATETIME,
            'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'already_processed_sample_ids': set(),
        }
        self.rec.attach_mock(self.patch('n6datasources.collectors.misp.LOGGER'), 'LOGGER')

        coro = collector._do_publish_sample(output_components, pub_sample_metadata)
        yielded = list(coro.__await__())

        assert self.rec.mock_calls == [
            call.publish_output(*output_components, exchange='sample'),
            call.LOGGER.info('Published the malware sample (id=%d).', 314159),
        ]
        assert inspect.iscoroutine(coro)
        assert yielded == ['FLUSH_OUT']
        assert self.saved_state == {
            'events_last_proc_datetime': MOCKED_NOW_DATETIME,
            'samples_last_proc_datetime': datetime.datetime(2017, 2, 9, 12),
            'already_processed_sample_ids': {314159},
        }


@expand
class TestMispCollector_adjust_state_from_py2_pickle(TestCaseMixin, unittest.TestCase):  # noqa

    def setUp(self):
        self.collector = object.__new__(MispCollector)
        self.patch('n6datasources.collectors.misp.gettz', lambda: gettz('Europe/Warsaw'))


    _EXAMPLE_PY2_STATE = {
        'events_publishing_datetime': datetime.datetime(2024, 1, 14, 22, 30, 59),
        'samples_publishing_datetime': datetime.datetime(2024, 1, 14, 22, 30, 59),
        'last_published_samples': [1, 2, 3],
    }
    _EXAMPLE_PY3_STATE = {
        'events_last_proc_datetime': datetime.datetime(2024, 1, 14, 21, 30, 59),
        'samples_last_proc_datetime': datetime.datetime(2024, 1, 14, 21, 30, 59),
        'already_processed_sample_ids': {1, 2, 3},
    }

    @foreach(
        param(
            py2_state=_EXAMPLE_PY2_STATE,
            expected_py3_state=_EXAMPLE_PY3_STATE,
        ).label('Winter time'),

        param(
            py2_state=_EXAMPLE_PY2_STATE | {
                'events_publishing_datetime': datetime.datetime(2024, 3, 31, 3, 30, 59),
                'samples_publishing_datetime': datetime.datetime(2024, 3, 31, 1, 45, 1),
            },
            expected_py3_state=_EXAMPLE_PY3_STATE | {
                'events_last_proc_datetime': datetime.datetime(2024, 3, 31, 1, 30, 59),
                'samples_last_proc_datetime': datetime.datetime(2024, 3, 31, 0, 45, 1),
            },
        ).label('Winter-to-summer-time transition (DST start)'),

        param(
            py2_state=_EXAMPLE_PY2_STATE | {
                'events_publishing_datetime': datetime.datetime(2023, 8, 14, 13, 30, 59),
                'samples_publishing_datetime': datetime.datetime(2023, 8, 14, 1, 45, 1),
            },
            expected_py3_state=_EXAMPLE_PY3_STATE | {
                'events_last_proc_datetime': datetime.datetime(2023, 8, 14, 11, 30, 59),
                'samples_last_proc_datetime': datetime.datetime(2023, 8, 13, 23, 45, 1),
            },
        ).label('Summer time'),

        param(
            py2_state=_EXAMPLE_PY2_STATE | {
                'events_publishing_datetime': datetime.datetime(2023, 10, 29, 3, 30, 59),
                'samples_publishing_datetime': datetime.datetime(2023, 10, 29, 2, 45, 1),
            },
            expected_py3_state=_EXAMPLE_PY3_STATE | {
                'events_last_proc_datetime': datetime.datetime(2023, 10, 29, 2, 30, 59),
                'samples_last_proc_datetime': datetime.datetime(2023, 10, 29, 0, 45, 1),
            },
        ).label('Summer-to-winter-time transition (DST end)'),
    )
    def test_ok(self, py2_state, expected_py3_state):
        py2_state = copy.deepcopy(py2_state)  # (<- just defensive programming)

        py3_state = self.collector.adjust_state_from_py2_pickle(py2_state)

        assert py3_state == expected_py3_state


    _EX = _EXAMPLE_PY2_STATE

    @foreach(
        param(
            py2_state=_EX | {'illegal_key': 42},
            expected_error_msg=(
                "unexpected set of Py2 state keys: "
                "'events_publishing_datetime', 'samples_publishing_datetime', "
                "'last_published_samples', 'illegal_key'"
            ),
        ),
        param(
            py2_state={
                k: v for k, v in _EX.items()
                if k != 'samples_publishing_datetime'
            },
            expected_error_msg=(
                "unexpected set of Py2 state keys: "
                "'events_publishing_datetime', 'last_published_samples'"
            ),
        ),
        param(
            py2_state=_EXAMPLE_PY3_STATE,
            expected_error_msg=(
                "unexpected set of Py2 state keys: "
                "'events_last_proc_datetime', 'samples_last_proc_datetime', "
                "'already_processed_sample_ids'"
            ),
        ),
        param(
            py2_state=_EX | {'events_publishing_datetime': 42},
            expected_error_msg=(
                "unexpected type(py2_state['events_publishing_datetime'])=<class 'int'>"
            ),
        ),
        param(
            py2_state=_EX | {'samples_publishing_datetime': '2023-10-29T02:45:01'},
            expected_error_msg=(
                "unexpected type(py2_state['samples_publishing_datetime'])=<class 'str'>"
            ),
        ),
        param(
            py2_state=_EX | {'last_published_samples': {1, 2, 3}},
            expected_error_msg=(
                "unexpected type(py2_state['last_published_samples'])=<class 'set'>"
            ),
        ),
        param(
            py2_state=_EX | {'last_published_samples': [1, '2', 3]},
            expected_error_msg=(
                "unexpected non-int value(s) found in "
                "py2_state['last_published_samples']=[1, '2', 3]"
            ),
        ),
        param(
            py2_state=_EX | {
                'events_publishing_datetime': datetime.datetime(2024, 1, 14, 22, 30, 59,
                                                                tzinfo=datetime.timezone.utc),
            },
            expected_error_msg=(
                "unexpected non-None tzinfo of py2_state['events_publishing_datetime']="
                "datetime.datetime(2024, 1, 14, 22, 30, 59, tzinfo=datetime.timezone.utc)"
            ),
        ),
        param(
            py2_state=_EX | {
                'samples_publishing_datetime': datetime.datetime(2024, 1, 14, 22, 30, 59,
                                                                 tzinfo=datetime.timezone.utc),
            },
            expected_error_msg=(
                "unexpected non-None tzinfo of py2_state['samples_publishing_datetime']="
                "datetime.datetime(2024, 1, 14, 22, 30, 59, tzinfo=datetime.timezone.utc)"
            ),
        ),
    )
    def test_error_for_unexpected_py2_state_content(self, py2_state, expected_error_msg):
        py2_state = copy.deepcopy(py2_state)  # (<- just defensive programming)
        with self.assertRaises(NotImplementedError) as exc_context:

            self.collector.adjust_state_from_py2_pickle(py2_state)

        assert str(exc_context.exception) == expected_error_msg

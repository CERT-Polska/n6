#  Copyright (c) 2021 NASK. All rights reserved.

from n6lib.auth_api import EVENT_DATA_RESOURCE_IDS
from n6lib.pyramid_commons import N6LimitedStreamView
from n6portal import RESOURCES


def test_data_resource_ids():
    assert {res.resource_id for res in RESOURCES
            if res.view_base is N6LimitedStreamView} == EVENT_DATA_RESOURCE_IDS

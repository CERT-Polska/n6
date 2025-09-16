# Copyright (c) 2013-2021 NASK. All rights reserved.

import unittest
from datetime import (
    datetime as dt,
    timedelta,
)
try:
    # Py3
    from unittest.mock import (
        MagicMock,
        Mock,
        patch,
        sentinel as sen,
    )
except ImportError:
    # Py2
    from mock import (
        MagicMock,
        Mock,
        patch,
        sentinel as sen,
    )
from urllib.parse import quote_plus

from pyramid.httpexceptions import HTTPTemporaryRedirect
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.auth_api import EVENT_DATA_RESOURCE_IDS
from n6lib.data_spec import N6DataSpec
from n6lib.unit_test_helpers import (
    MethodProxy,
    RequestHelperMixin,
)
from n6restapi import (
    DATA_RESOURCES,
    RestAPIViewBase,
)


def _quoted_tuple(*values):
    return tuple(str(quote_plus(str(v))) for v in values)                        #3: remove the outer `str...`


def test_data_resource_ids():
    assert {res.resource_id for res in DATA_RESOURCES} == EVENT_DATA_RESOURCE_IDS


@expand
class TestRestAPIViewBase(unittest.TestCase):

    REQUEST_PATH_URL = '/foo'
    DEFAULT_DELTA = timedelta(days=3)  # note: for these test it is 3 days (not 7 days)
    SAM_DELTA = RestAPIViewBase.SAFE_ACTIVE_MIN_DELTA

    UTC_NOW = dt(2015, 8, 31, 16, 22, 44)
    BEFORE_UTC_NOW = dt(2015, 8, 30, 15, 57, 42)
    AFTER_UTC_NOW = dt(2015, 9, 1, 14, 56, 41)

    cases__get_redirect_url_if_no_time_min = [
        param(
            request_query_string='...',
            cleaned_param_dict={'time.min': sen.ANYTHING},
            expected_redirect_url=None,
        ).label('time.min is present'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'time.min': sen.ANYTHING,
                'time.max': sen.ANYTHING,
                'time.until': sen.ANYTHING,
                'modified.min': sen.ANYTHING,
                'modified.max': sen.ANYTHING,
                'modified.until': sen.ANYTHING,
                'active.min': sen.ANYTHING,
                'active.max': sen.ANYTHING,
                'active.until': sen.ANYTHING,
            },
            expected_redirect_url=None,
        ).label('time.min is present, others as well...'),

        param(
            request_query_string='...',
            cleaned_param_dict={},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('non-empty qs'),

        param(
            request_query_string='',
            cleaned_param_dict={},
            expected_redirect_url='/foo?time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('empty qs'),
    ]

    # time.max/until
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={'time.max': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `time.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA),
        ).label('time.max < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'time.until': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `time.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA),
        ).label('time.until < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'time.max': [AFTER_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('time.max > utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'time.until': [AFTER_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('time.until > utcnow()'),
    ]

    # modified.min
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={'modified.min': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA),
        ).label('modified.min < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'modified.min': [AFTER_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('modified.min > utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW],
                'modified.max': sen.ANYTHING,
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA),
        ).label('modified.min < utcnow(), irrelevant modified.max'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [AFTER_UTC_NOW],
                'modified.until': sen.ANYTHING,
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('modified.min > utcnow(), irrelevant modified.until'),
    ]

    # modified.max/until
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={'modified.max': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - DEFAULT_DELTA,
            ),
        ).label('modified.max < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'modified.until': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - DEFAULT_DELTA,
            ),
        ).label('modified.until < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'modified.max': [BEFORE_UTC_NOW + DEFAULT_DELTA]},
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                BEFORE_UTC_NOW,
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() and '
            'modified.max < utcnow() + default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={'modified.until': [BEFORE_UTC_NOW + DEFAULT_DELTA]},
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                BEFORE_UTC_NOW,
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.until > utcnow() and '
            'modified.until < utcnow() + default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA]},
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                AFTER_UTC_NOW,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label('modified.max > utcnow() + default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={'modified.until': [AFTER_UTC_NOW + DEFAULT_DELTA]},
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                AFTER_UTC_NOW,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label('modified.until > utcnow() + default_delta'),
    ]

    # active.min
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={'active.min': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - SAM_DELTA),
        ).label('active.min'),

        param(
            request_query_string='...',
            cleaned_param_dict={'active.min': [AFTER_UTC_NOW]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `active.min`:
                AFTER_UTC_NOW - SAM_DELTA),
        ).label(
            'active.min > utcnow() and '
            'active.min < utcnow() + SAFE_ACTIVE_MIN_DELTA - default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={'active.min': [BEFORE_UTC_NOW + SAM_DELTA]},
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('active.min > utcnow() + SAFE_ACTIVE_MIN_DELTA - default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'active.min': [BEFORE_UTC_NOW],
                'active.max': sen.ANYTHING,
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - SAM_DELTA),
        ).label('active.min, irrelevant active.max'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'active.min': [BEFORE_UTC_NOW + SAM_DELTA],
                'active.until': sen.ANYTHING,
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label('active.min..., irrelevant active.until'),
    ]

    # active.max/until
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={'active.max': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - SAM_DELTA,
            ),
        ).label('active.max < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'active.until': [BEFORE_UTC_NOW]},
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - SAM_DELTA,
            ),
        ).label('active.until < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={'active.max': [BEFORE_UTC_NOW + DEFAULT_DELTA]},
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                BEFORE_UTC_NOW,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - SAM_DELTA,
            ),
        ).label(
            'active.max > utcnow() and '
            'active.max < utcnow() + default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={'active.until': [BEFORE_UTC_NOW + SAM_DELTA]},
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.until`:
                BEFORE_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'active.until > utcnow() + default_delta and '
            'active.until < utcnow() + SAFE_ACTIVE_MIN_DELTA'),

        param(
            request_query_string='...',
            cleaned_param_dict={'active.max': [AFTER_UTC_NOW + SAM_DELTA]},
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label('active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA'),
    ]

    # modified.min and active.min (and time.max)
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW],
                'active.min': [BEFORE_UTC_NOW],
                'time.max': [BEFORE_UTC_NOW + SAM_DELTA],
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - SAM_DELTA),
        ).label(
            'modified.min < utcnow() and '
            'active.min == modified.min and '
            'time.max > utcnow() + default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW],
                'active.min': [AFTER_UTC_NOW + SAM_DELTA],
                'modified.max': sen.ANYTHING,
                'active.until': sen.ANYTHING,
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA),
        ).label(
            'modified.min < utcnow(), '
            'active.min > utcnow() + SAFE_ACTIVE_MIN_DELTA, '
            'irrelevant modified.max & active.until'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW + SAM_DELTA],
                'active.min': [AFTER_UTC_NOW + SAM_DELTA],
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA),
        ).label(
            'modified.min > utcnow(), '
            'active.min > utcnow() + SAFE_ACTIVE_MIN_DELTA'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW + SAM_DELTA],
                'active.min': [AFTER_UTC_NOW + SAM_DELTA],
                'time.until': [BEFORE_UTC_NOW],
            },
            expected_redirect_url='/foo?...&time.min=%s' % _quoted_tuple(
                # `time.min` derived from `time.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA),
        ).label(
            'modified.min > utcnow(), '
            'active.min > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until < utcnow()'),
    ]

    # various max/until mixes...
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [BEFORE_UTC_NOW],
                'active.until': [BEFORE_UTC_NOW],
            },
            expected_redirect_url='/foo?...&modified.min=%s&active.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `active.min` derived from `active.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - SAM_DELTA,
            ),
        ).label(
            'modified.max < utcnow() and '
            'active.until == modified.max'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.until': [BEFORE_UTC_NOW],
                'active.max': [BEFORE_UTC_NOW],
                'time.max': [BEFORE_UTC_NOW - 2*SAM_DELTA],
            },
            expected_redirect_url='/foo?...&modified.min=%s&active.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `active.min` derived from `active.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `time.max`:
                BEFORE_UTC_NOW - 2*SAM_DELTA - DEFAULT_DELTA,
            ),
        ).label(
            'modified.until < utcnow() and '
            'active.max == modified.until and '
            'time.max much earlier'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [BEFORE_UTC_NOW],
                'time.max': [BEFORE_UTC_NOW - 2*SAM_DELTA],
            },
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `time.max`:
                BEFORE_UTC_NOW - 2*SAM_DELTA - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max < utcnow() and '
            'time.max much earlier'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.until': [BEFORE_UTC_NOW + DEFAULT_DELTA],
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
                'time.until': [AFTER_UTC_NOW + 2*SAM_DELTA],
            },
            expected_redirect_url='/foo?...&modified.min=%s&active.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                BEFORE_UTC_NOW,
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.until > utcnow() and '
            'modified.until < utcnow() + default_delta and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until much later'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA],
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
            },
            expected_redirect_url='/foo?...&modified.min=%s&active.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                AFTER_UTC_NOW,
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() + default_delta and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA],
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
                'time.until': [AFTER_UTC_NOW],
            },
            expected_redirect_url='/foo?...&modified.min=%s&active.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                AFTER_UTC_NOW,
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() + default_delta and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until > utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
                'time.until': [BEFORE_UTC_NOW],
            },
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from `time.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until < utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                # `modified.min` derived from `modified.max`:
                'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA],
                # `active.min` derived from `active.max`:
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
                # `time.min` derived from `time.until`:
                'time.until': [BEFORE_UTC_NOW],
            },
            expected_redirect_url='/foo?...&modified.min=%s&active.min=%s&time.min=%s' % _quoted_tuple(
                AFTER_UTC_NOW,
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() + default_delta and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until < utcnow()'),
    ]

    # various min/max/until mixes
    cases__get_redirect_url_if_no_time_min += [
        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW],
                'modified.max': sen.ANYTHING,
                'active.max': [BEFORE_UTC_NOW],
            },
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - SAM_DELTA,
            ),
        ).label(
            'modified.min < utcnow() and '
            'active.max == modified.min, '
            'irrelevant modified.max'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.until': [AFTER_UTC_NOW],
                'active.min': [BEFORE_UTC_NOW],
                'active.until': sen.ANYTHING,
            },
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                AFTER_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - SAM_DELTA,
            ),
        ).label(
            'modified.until > utcnow() and '
            'active.min < utcnow(), '
            'irrelevant active.until'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.until': [BEFORE_UTC_NOW],
                'active.min': [BEFORE_UTC_NOW],
                'active.until': sen.ANYTHING,
                'time.max': [BEFORE_UTC_NOW - 2*SAM_DELTA],
            },
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.until`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
                # `time.min` derived from `time.max`:
                BEFORE_UTC_NOW - 2*SAM_DELTA - DEFAULT_DELTA,
            ),
        ).label(
            'modified.until < utcnow() and '
            'active.min == modified.until, '
            'irrelevant active.until and '
            'time.max much earlier'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [BEFORE_UTC_NOW],
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
                'time.until': [AFTER_UTC_NOW + 2*SAM_DELTA],
            },
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from `modified.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.min < utcnow() and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until much later'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [AFTER_UTC_NOW],
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
            },
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.min > utcnow() and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.min': [AFTER_UTC_NOW],
                'active.max': [AFTER_UTC_NOW + SAM_DELTA],
                'time.until': [AFTER_UTC_NOW],
            },
            expected_redirect_url='/foo?...&active.min=%s&time.min=%s' % _quoted_tuple(
                # `active.min` derived from `active.max`:
                AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.min > utcnow() and '
            'active.max > utcnow() + SAFE_ACTIVE_MIN_DELTA and '
            'time.until > utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA],
                'active.min': [BEFORE_UTC_NOW + SAM_DELTA - DEFAULT_DELTA],
                'time.max': [BEFORE_UTC_NOW - DEFAULT_DELTA],
            },
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                AFTER_UTC_NOW,
                # `time.min` derived from `time.max`:
                BEFORE_UTC_NOW - DEFAULT_DELTA - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() + default_delta and '
            'active.min > utcnow() and '
            'active.min < utcnow() + SAFE_ACTIVE_MIN_DELTA - default_delta and '
            'time.max < utcnow() - default_delta'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA],
                'active.min': [BEFORE_UTC_NOW + SAM_DELTA - DEFAULT_DELTA],
                'time.max': [AFTER_UTC_NOW],
            },
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                AFTER_UTC_NOW,
                # `time.min` derived from `active.min`:
                BEFORE_UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() + default_delta and '
            'active.min > utcnow() and '
            'active.min < utcnow() + SAFE_ACTIVE_MIN_DELTA - default_delta and '
            'time.max > utcnow()'),

        param(
            request_query_string='...',
            cleaned_param_dict={
                'modified.max': [AFTER_UTC_NOW + DEFAULT_DELTA],
                'active.min': [AFTER_UTC_NOW + SAM_DELTA - DEFAULT_DELTA],
                'time.max': [AFTER_UTC_NOW],
            },
            expected_redirect_url='/foo?...&modified.min=%s&time.min=%s' % _quoted_tuple(
                # `modified.min` derived from `modified.max`:
                AFTER_UTC_NOW,
                # `time.min` derived from utcnow():
                UTC_NOW - DEFAULT_DELTA,
            ),
        ).label(
            'modified.max > utcnow() + default_delta and '
            'active.min > utcnow() + SAFE_ACTIVE_MIN_DELTA - default_delta and '
            'time.max > utcnow()'),
    ]

    @foreach(cases__get_redirect_url_if_no_time_min)
    def test__get_redirect_url_if_no_time_min(self,
                                              request_query_string,
                                              cleaned_param_dict,
                                              expected_redirect_url):
        mock = MagicMock()
        mock.request.path_url = self.REQUEST_PATH_URL
        mock.request.query_string = request_query_string
        meth = MethodProxy(
            RestAPIViewBase,
            mock,
            class_attrs=['SAFE_ACTIVE_MIN_DELTA', '_get_redirect_url'])

        with patch('n6restapi.utcnow', return_value=self.UTC_NOW):
            actual_redirect_url = meth.get_redirect_url_if_no_time_min(
                cleaned_param_dict,
                self.DEFAULT_DELTA)

        self.assertEqual(actual_redirect_url, expected_redirect_url)


class TestRestAPIViewBase_prepare_params(RequestHelperMixin, unittest.TestCase):

    __USER_ID = 'user'
    __ORG_ID = 'org.com'

    @classmethod
    def get_concrete_view_class_kwargs(cls, view_class, request):
        d = super(TestRestAPIViewBase_prepare_params,
                  cls).get_concrete_view_class_kwargs(view_class, request)
        d.update({
            'resource_id': '/search/events',
            'data_spec': N6DataSpec(),
            'data_backend_api_method': 'search_events',
            'renderers': 'json',
        })
        return d

    @classmethod
    def _make_get_prepared_params_method(cls, view_class, request):
        def get_params():
            view_instance = cls.make_view_instance(view_class, request)
            return view_instance.prepare_params()
        return get_params

    @classmethod
    def create_request(cls, view_class, **kwargs):
        request = super(TestRestAPIViewBase_prepare_params,
                        cls).create_request(view_class, **kwargs)
        request.get_prepared_params = cls._make_get_prepared_params_method(view_class, request)
        request.matchdict['renderer'] = 'json'
        request.auth_data = {'user_id': cls.__USER_ID, 'org_id': cls.__ORG_ID}
        return request

    def setUp(self):
        access_info_dict = {
            'rest_api_resource_limits': {
                '/search/events': {
                    'queries_limit': None,
                    'window': 3600,
                    'request_parameters': None,
                    'max_days_old': 100,
                    'results_limit': None,
                },
            },
            'rest_api_full_access': False,
            'access_zone_conditions': {
                'search': sen.search_conds,
            },
        }
        self._config = self.prepare_pyramid_unittesting()
        self._config.registry.auth_api = Mock()
        self._config.registry.auth_api.get_access_info.return_value = access_info_dict
        self._config.registry.auth_api.get_user_ids_to_org_ids.return_value = {
            self.__USER_ID: self.__ORG_ID,
        }

    def test_prepare_params__with_time_min(self):
        request = self.create_request(RestAPIViewBase, **{'time.min': '2020-01-01T12:00:00'})
        prepared_params = request.get_prepared_params()
        self.assertEqual(prepared_params, {u'time.min': [dt(2020, 1, 1, 12, 0)]})

    def test_prepare_params__without_time_min(self):
        request = self.create_request(RestAPIViewBase, **{})
        with self.assertRaises(HTTPTemporaryRedirect):
            request.get_prepared_params()

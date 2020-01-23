# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import unittest
from datetime import (
    datetime as dt,
    timedelta,
)
from urllib import quote_plus

from unittest_expander import expand, foreach, param

from mock import (
    MagicMock,
    patch,
    sentinel as sen,
)

from n6lib.unit_test_helpers import MethodProxy
from n6web import RestAPIViewBase


def _quoted_tuple(*values):
    return tuple(quote_plus(str(v)) for v in values)


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

        with patch('n6web.utcnow', return_value=self.UTC_NOW):
            actual_redirect_url = meth.get_redirect_url_if_no_time_min(
                cleaned_param_dict,
                self.DEFAULT_DELTA)

        self.assertEqual(actual_redirect_url, expected_redirect_url)

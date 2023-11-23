# Copyright (c) 2013-2023 NASK. All rights reserved.

import copy
import unittest
from datetime import datetime as dt
from unittest.mock import (
    MagicMock,
    patch,
    sentinel as sen,
)
from sqlalchemy import and_
from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6lib.data_backend_api import (
    LOGGER as module_logger,
    N6DataBackendAPI,
    _EventsQueryProcessor,
)
from n6lib.data_spec import N6DataSpec, N6InsideDataSpec
from n6lib.sqlalchemy_related_test_helpers import sqlalchemy_expr_to_str
from n6lib.unit_test_helpers import (
    MethodProxy,
    TestCaseMixin,
)


## TODO: more N6DataBackendAPI tests
## TODO: more _EventsQueryProcessor tests (__init__ etc.)


class Test_N6DataBackendAPI__delete_opt_prefixed_params(unittest.TestCase):

    def test(self):
        mock = MagicMock()
        meth = MethodProxy(N6DataBackendAPI, mock)
        params = {
            'name': 'foo-bar',
            'opt.primary': True,
            'time.min': [dt(2015, 1, 4)],
            'time.until': [dt(2015, 1, 5)],
        }
        expected_params = {
            'name': 'foo-bar',
            'time.min': [dt(2015, 1, 4)],
            'time.until': [dt(2015, 1, 5)],
        }
        meth._delete_opt_prefixed_params(params)
        self.assertEqual(params, expected_params)
        self.assertEqual(mock.mock_calls, [])


@expand
class Test_EventsQueryProcessor__get_key_to_query_func(unittest.TestCase):

    @foreach(
        param(data_spec_class=N6DataSpec),
        param(data_spec_class=N6InsideDataSpec),
    )
    def test(self, data_spec_class):
        cls = _EventsQueryProcessor
        data_spec = data_spec_class()
        _get_key_to_query_func = cls._get_key_to_query_func.func  # getting it without memoization
        with patch.object(cls, 'queried_model_class') as qmc_mock:
            key_to_query_func = _get_key_to_query_func(cls, data_spec)
        key_query = qmc_mock.key_query
        self.assertEqual(key_to_query_func, {
            'active.max': qmc_mock.active_bl_query,
            'active.min': qmc_mock.active_bl_query,
            'active.until': qmc_mock.active_bl_query,
            'asn': key_query,
            'category': key_query,
            'cc': key_query,
            'confidence': key_query,
            'dip': key_query,
            'dport': key_query,
            'fqdn': key_query,
            'fqdn.sub': qmc_mock.like_query,
            'id': key_query,
            'ip': key_query,
            'ip.net': qmc_mock.ip_net_query,
            'md5': key_query,
            'modified.max': qmc_mock.modified_query,
            'modified.min': qmc_mock.modified_query,
            'modified.until': qmc_mock.modified_query,
            'name': key_query,
            'origin': key_query,
            'proto': key_query,
            'replaces': key_query,
            'restriction': key_query,
            'rid': key_query,
            'sha1': key_query,
            'sha256': key_query,
            'source': key_query,
            'sport': key_query,
            'status': key_query,
            'target': key_query,
            'url': key_query,
            'url.sub': qmc_mock.like_query,
            'url.b64': qmc_mock.url_b64_experimental_query,
        })


@expand
class Test_EventsQueryProcessor_generate_query_results(unittest.TestCase):

    _UTCNOW = dt(2015, 1, 3, 17, 18, 19)

    # a helper that makes the expression query
    # reprs for a given time window (step)
    def _win(upper_op, upper, lower):
        return [
            ("event.time >= '{0}' AND "
             "event.time {1} '{2}'".format(
                 lower,
                 upper_op,
                 upper)),
            ("client_to_event.id = event.id AND "
             "client_to_event.time >= '{0}' AND "
             "client_to_event.time {1} '{2}'".format(
                 lower,
                 upper_op,
                 upper)),
            'event.time DESC',
        ]


    # typical cases
    cases_time_related_components_of_generated_queries = [
        param(
            given_time_constraints_items={
                'time.min': dt(2015, 1, 3, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-03 16:17:18',
            ),
        ).label('no time.max/until given, 1 window'),

        param(
            given_time_constraints_items={
                'time.max': dt(2015, 1, 5, 14, 15, 16),
                'time.min': dt(2015, 1, 4, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-05 14:15:16',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.max given, 1 window'),

        param(
            given_time_constraints_items={
                'time.until': dt(2015, 1, 5, 14, 15, 16, 999999),
                'time.min': dt(2015, 1, 4, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-05 14:15:16.999999',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.until given, 1 window'),

        param(
            given_time_constraints_items={
                'time.min': dt(2015, 1, 2, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-02 18:18:19',
            ) + _win(
                upper_op='<',
                upper='2015-01-02 18:18:19',
                lower='2015-01-02 16:17:18',
            ),
        ).label('no time.max/until given, several windows'),

        param(
            given_time_constraints_items={
                'time.max': dt(2015, 1, 5, 14, 15, 16),
                'time.min': dt(2015, 1, 2, 16, 17, 18, 1),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-05 14:15:16',
                lower='2015-01-04 14:15:16',
            ) + _win(
                upper_op='<',
                upper='2015-01-04 14:15:16',
                lower='2015-01-03 14:15:16',
            ) + _win(
                upper_op='<',
                upper='2015-01-03 14:15:16',
                lower='2015-01-02 16:17:18.000001',
            ),
        ).label('time.max given, several windows'),

        param(
            given_time_constraints_items={
                'time.until': dt(2015, 1, 2, 14, 15, 16),
                'time.min': dt(2014, 12, 30, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-02 14:15:16',
                lower='2015-01-01 14:15:16',
            ) + _win(
                upper_op='<',
                upper='2015-01-01 14:15:16',
                lower='2014-12-31 14:15:16',
            ) + _win(
                upper_op='<',
                upper='2014-12-31 14:15:16',
                lower='2014-12-30 16:17:18',
            ),
        ).label('time.until given, several windows'),
    ]

    # special cases: time.{max,until} - time.min == multiplicity of window size
    cases_time_related_components_of_generated_queries.extend([
        param(
            given_time_constraints_items={
                'time.min': dt(2015, 1, 2, 18, 18, 19),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-02 18:18:19',
            ),
        ).label('no time.max/until given, 1 window, delta == window'),

        param(
            given_time_constraints_items={
                'time.max': dt(2015, 1, 5, 16, 17, 18),
                'time.min': dt(2015, 1, 4, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-05 16:17:18',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.max given, 1 window, delta == window'),

        param(
            given_time_constraints_items={
                'time.until': dt(2015, 1, 5),
                'time.min': dt(2015, 1, 4),
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-05 00:00:00',
                lower='2015-01-04 00:00:00',
            ),
        ).label('time.until given, 1 window, delta == window'),

        param(
            given_time_constraints_items={
                'time.min': dt(2015, 1, 1, 18, 18, 19),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-02 18:18:19',
            ) + _win(
                upper_op='<',
                upper='2015-01-02 18:18:19',
                lower='2015-01-01 18:18:19',
            ),
        ).label('no time.max/until given, several windows, delta == n * window'),

        param(
            given_time_constraints_items={
                'time.max': dt(2015, 1, 2, 14, 15, 16, 999999),
                'time.min': dt(2014, 12, 30, 14, 15, 16, 999999),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-02 14:15:16.999999',
                lower='2015-01-01 14:15:16.999999',
            ) + _win(
                upper_op='<',
                upper='2015-01-01 14:15:16.999999',
                lower='2014-12-31 14:15:16.999999',
            ) + _win(
                upper_op='<',
                upper='2014-12-31 14:15:16.999999',
                lower='2014-12-30 14:15:16.999999',
            ),
        ).label('time.max given, several windows, delta == n * window'),

        param(
            given_time_constraints_items={
                'time.until': dt(2015, 1, 5),
                'time.min': dt(2015, 1, 2),
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-05 00:00:00',
                lower='2015-01-04 00:00:00',
            ) + _win(
                upper_op='<',
                upper='2015-01-04 00:00:00',
                lower='2015-01-03 00:00:00',
            ) + _win(
                upper_op='<',
                upper='2015-01-03 00:00:00',
                lower='2015-01-02 00:00:00',
            ),
        ).label('time.until given, several windows, delta == n * window'),
    ])

    # special cases: time.min == time.{max,until}
    cases_time_related_components_of_generated_queries.extend([
        param(
            given_time_constraints_items={
                'time.min': dt(2015, 1, 3, 18, 18, 19),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-03 18:18:19',
            ),
        ).label('time_min == utcnow() + 1h, no time.max/until given'),

        param(
            given_time_constraints_items={
                'time.max': dt(2015, 1, 4, 16, 17, 18),
                'time.min': dt(2015, 1, 4, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-04 16:17:18',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.min == time.max'),

        param(
            given_time_constraints_items={
                'time.until': dt(2015, 1, 4, 16, 17, 18, 999999),
                'time.min': dt(2015, 1, 4, 16, 17, 18, 999999),
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-04 16:17:18.999999',
                lower='2015-01-04 16:17:18.999999',
            ),
        ).label('time.min == time.until'),
    ])

    # special cases: time.min > time.{max,until}
    cases_time_related_components_of_generated_queries.extend([
        param(
            given_time_constraints_items={
                'time.min': dt(2015, 1, 3, 18, 18, 19, 1),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-03 18:18:19.000001',
            ),
        ).label('time_min > utcnow() + 1h, no time.max/until given'),

        param(
            given_time_constraints_items={
                'time.max': dt(2015, 1, 4, 16, 17, 18),
                'time.min': dt(2015, 1, 7, 18, 19, 20),
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-04 16:17:18',
                lower='2015-01-07 18:19:20',
            ),
        ).label('time.min > time.max'),

        param(
            given_time_constraints_items={
                'time.until': dt(2015, 1, 4, 16, 17, 18),
                'time.min': dt(2015, 1, 5, 16, 17, 18),
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-04 16:17:18',
                lower='2015-01-05 16:17:18',
            ),
        ).label('time.min > time.until'),
    ])

    @foreach(cases_time_related_components_of_generated_queries)
    def test_time_related_components_of_generated_queries(self,
                                                          given_time_constraints_items,
                                                          expected_query_expr_reprs):
        mock = MagicMock()
        meth = MethodProxy(
            _EventsQueryProcessor,
            mock,
            class_attrs=[
                # for them, the actual members/methods (not mocks) will be used
                # * class constants:
                'queried_model_class',
                'client_asoc_model_class',
                # * methods:
                '_prepare_result_production_tools',
                '_fetch_rows_from_db',
                '_time_comparisons_per_step',
                '_fetch_rows_for_single_step',
                '_build_query_base_for_single_step',
                '_build_actual_query',
            ])
        actual_query_expr_reprs = []
        and_mock = self._make_mock_of_sqlalchemy_and(actual_query_expr_reprs)
        mock._query_base = self._make_mock_of_query_base(actual_query_expr_reprs)
        mock._day_step = 1
        mock._opt_limit = None
        mock._time_constraints = (
            given_time_constraints_items['time.min'],
            given_time_constraints_items.get('time.max'),
            given_time_constraints_items.get('time.until'))
        with patch('n6lib.data_backend_api.and_', and_mock), \
             patch('n6lib.data_backend_api.utcnow', return_value=self._UTCNOW):
            list(meth.generate_query_results())
        self.assertEqual(actual_query_expr_reprs, expected_query_expr_reprs)

    def _make_mock_of_sqlalchemy_and(self, actual_query_expr_reprs):
        def side_effect(*sqlalchemy_conds):
            cond = and_(*sqlalchemy_conds)
            cond_str = sqlalchemy_expr_to_str(cond).replace('`', '')
            actual_query_expr_reprs.append(cond_str)
            return sen.and_
        and_mock = MagicMock()
        and_mock.side_effect = side_effect
        return and_mock

    def _make_mock_of_query_base(self, actual_query_expr_reprs):
        def side_effect_of_order_by(sqlalchemy_expr):
            expr_str = sqlalchemy_expr_to_str(sqlalchemy_expr).replace('`', '')
            actual_query_expr_reprs.append(expr_str)
            return query_mock
        query_mock = MagicMock()
        query_mock.filter.return_value = query_mock
        query_mock.outerjoin.return_value = query_mock
        query_mock.order_by.side_effect = side_effect_of_order_by
        return query_mock


    ## TODO: test other aspects of the generate_query_results() method...


@expand
class Test_EventsQueryProcessor__preprocess_result_dict(TestCaseMixin, unittest.TestCase):

    @paramseq
    def cases(cls):
        yield param(
            # 'SY:'-prefixed `url`, no `custom`
            # -> result: nothing
            raw_result_dict={
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url` \('SY:co\\u015btam'\) starts with 'SY:' but no `url_data`!",
            ],
            expected_result=None,
        ).label(
        "(01) 'SY:'-prefixed `url`, no `custom`")

        yield param(
            # 'SY:'-prefixed `url`, no `custom`, unrelated data
            # -> result: nothing
            #
            # [general remark: the *unrelated data* stuff is generally
            # irrelevant for the core logic the tests provided by this
            # class concern; many of them include *unrelated data*, but
            # this is done just to show that those data do not interfere
            # with that logic, or -- when applicable -- that they are
            # passed through without problems...]
            raw_result_dict={
                'url': 'SY:cośtam',
                'foo': 'bar',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url` \('SY:co\\u015btam'\) starts with 'SY:' but no `url_data`!",
            ],
            expected_result=None,
        ).label(
        "(02) 'SY:'-prefixed `url`, no `custom`, unrelated data")

        yield param(
            # 'SY:'-prefixed `url`, `custom` without `url_data`
            # -> result: nothing
            raw_result_dict={
                'custom': {'spam': 'ham'},
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url` \('SY:co\\u015btam'\) starts with 'SY:' but no `url_data`!",
            ],
            expected_result=None,
        ).label(
        "(03) 'SY:'-prefixed `url`, `custom` without `url_data`")

        yield param(
            # 'SY:'-prefixed `url`, `custom` without `url_data`, unrelated data
            # -> result: nothing
            raw_result_dict={
                'custom': {'spam': 'ham'},
                'url': 'SY:cośtam',
                'foo': 'bar',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url` \('SY:co\\u015btam'\) starts with 'SY:' but no `url_data`!",
            ],
            expected_result=None,
        ).label(
        "(04) 'SY:'-prefixed `url`, `custom` without `url_data`, unrelated data")

        yield param(
            # `custom` with `url_data`, no 'url'
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'orig_b64': 'eA==',
                        'norm_brief': 'emru',
                    },
                },
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \(None\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(05) `custom` with `url_data`, no 'url'")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # `custom` with `url_data`, no 'url'
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'url_orig': 'eA==',
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                },
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \(None\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(06) `custom` with `url_data`, no 'url' [@legacy]")

        yield param(
            # `custom` with `url_data`, unrelated data, no 'url'
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'orig_b64': 'eA==',
                        'norm_brief': 'emru',
                    },
                },
                'foo': 'bar',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \(None\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(07) `custom` with `url_data`, unrelated data, no 'url'")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # `custom` with `url_data`, unrelated data, no 'url'
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'url_orig': 'eA==',
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                },
                'foo': 'bar',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \(None\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(08) `custom` with `url_data`, unrelated data, no 'url' [@legacy]")

        yield param(
            # `url` without 'SY:' prefix, `custom` with `url_data`
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'orig_b64': 'eA==',
                        'norm_brief': 'emru',
                    },
                },
               'url': 'foo:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \('foo:.*'\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(09) `url` without 'SY:' prefix, `custom` with `url_data`")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # `url` without 'SY:' prefix, `custom` with `url_data`
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'url_orig': 'eA==',
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                },
                'url': 'foo:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \('foo:.*'\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(10) `url` without 'SY:' prefix, `custom` with `url_data` [@legacy]")

        yield param(
            # `url` without 'SY:' prefix, `custom` with `url_data`, unrelated data
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'orig_b64': 'eA==',
                        'norm_brief': 'emru',
                    },
                },
                'url': 'foo:cośtam',
                'foo': 'bar',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \('foo:.*'\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(11) `url` without 'SY:' prefix, `custom` with `url_data`, unrelated data")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # `url` without 'SY:' prefix, `custom` with `url_data`, unrelated data
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'url_orig': 'eA==',
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                },
                'url': 'foo:cośtam',
                'foo': 'bar',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` present.*but `url` \('foo:.*'\) does not start with 'SY:'!",
            ],
            expected_result=None,
        ).label(
        "(12) `url` without 'SY:' prefix, `custom` with `url_data`, unrelated data [@legacy]")

        yield param(
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (not a dict)
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': ['something'],
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\['something'\]\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(13) `'SY:'-prefixed `url`, custom` with `url_data` which is not valid "
        "(not a dict)")

        yield param(
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (missing keys),
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'norm_brief': 'emru',
                    },
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\{'norm_brief': 'emru'\}\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(14) `'SY:'-prefixed `url`, custom` with `url_data` which is not valid "
        "(missing keys)")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (missing keys)
            # -> result: nothing
            raw_result_dict={
                 'custom': {
                    'url_data': {
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\{'url_norm_opts': \{.*\}\}\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(15) 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid "
        "(missing keys) [@legacy]")

        yield param(
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (illegal keys)
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'orig_b64': 'eA==',
                        'norm_brief': 'emru',
                        'spam': 'ham',
                    },
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\{.*\}\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(16) 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid "
        "(illegal keys)")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (illegal keys)
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'url_orig': 'eA==',
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                        'spam': 'ham',
                    },
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\{.*\}\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(17) 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid "
        "(illegal keys) [@legacy]")

        yield param(
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (empty `orig_b64`)
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'orig_b64': '',
                        'norm_brief': 'emru',
                    },
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\{.*\}\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(18) `custom` with `url_data` which is not valid "
        "(empty `orig_b64`)")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            # 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid (empty `url_orig`)
            # -> result: nothing
            raw_result_dict={
                'custom': {
                    'url_data': {
                        'url_orig': '',
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                },
                'url': 'SY:cośtam',
            },
            expected_log_regexes=[
                r"^ERROR:.*`url_data` \(\{.*\}\) is not valid!",
            ],
            expected_result=None,
        ).label(
        "(19) 'SY:'-prefixed `url`, `custom` with `url_data` which is not valid "
        "(empty `url_orig`) [@legacy]")

        yield param(
            # unrelated data, no `url`, no `custom`
            # -> result: unrelated data
            raw_result_dict={
                'foo': 'bar',
            },
            expected_result={
                'foo': 'bar',
            },
        ).label(
        "(20) unrelated data, no `url`, no `custom`")

        yield param(
            # unrelated data, no `url`, `custom` without `url_data`
            # -> result: unrelated data, `custom`
            raw_result_dict={
                'custom': {'spam': 'ham'},
                'foo': 'bar',
            },
            expected_result={
                'custom': {'spam': 'ham'},
                'foo': 'bar',
            },
        ).label(
        "(21) unrelated data, no `url`, `custom` without `url_data`")

        yield param(
            # `url` without 'SY:' prefix, unrelated data, no `custom`
            # -> result: `url`, unrelated data
            raw_result_dict={
                'url': 'something-else',
                'foo': 'bar',
            },
            expected_result={
                'url': 'something-else',
                'foo': 'bar',
            },
        ).label(
        "(22) `url` without 'SY:' prefix, unrelated data, no `custom`")

        yield param(
            # `url` without 'SY:' prefix, unrelated data, `custom` without `url_data`
            # -> result: `url`, unrelated data, `custom`
            raw_result_dict={
                'custom': {'spam': 'ham'},
                'url': 'something-else',
                'foo': 'bar',
            },
            expected_result={
                'custom': {'spam': 'ham'},
                'url': 'something-else',
                'foo': 'bar',
            },
        ).label(
        "(23) `url` without 'SY:' prefix, unrelated data, `custom` without `url_data`")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80/?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006P3E97bOd'
                                     '7aCAJTNELSU0RC0lNUQtTmkhPyPtr7_tv7_ts4w='),

                        # (`empty_path_slash`, `merge_surrogate_pairs`,
                        #  `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'emru',
                    },
                },
            },
            expected_result={
                'url': 'http://Ćma.example.com/?q=\udcdd\ud800%3D-%4D-%5D-Ni!?#\U0010FFFF\udccc',
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(24) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, 'emru')")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `unicode_str`
            # * here lack of `remove_ipv6_zone` changes nothing, as this
            #   URL does not contain IPv6 address
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELU5pIT8j7a-_7b-_7bOM'),

                        # (`empty_path_slash`, `merge_surrogate_pairs`, `unicode_str`)
                        'norm_brief': 'emu',
                    },
                },
            },
            expected_result={
                'url': 'http://Ćma.example.com/?q=\udcdd\ud800%3D-%4D-%5D-Ni!?#\U0010FFFF\udccc',
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(25) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, 'emu')")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized + coerced to `str`,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`
            # * here lack of `unicode_str` does not prevent matching
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELU5pIT8j7a-_7b-_7bOM'),

                        # (`empty_path_slash`, `merge_surrogate_pairs`)
                        'norm_brief': 'em',
                    },
                },
            },
            expected_result={
                'url': (
                    # note: lack of the `unicode_str` option means that
                    # the result of normalization is a `bytes` object
                    # (which is then coerced to `str`, just for the
                    # "url" result item, by applying the helper function
                    # `as_str_with_minimum_esc()`; the bytes which encode
                    # unpaired surrogates are escaped by it using the
                    # `\x...` notation)
                    'http://Ćma.example.com/?q=\\xed\\xb3\\x9d\\xed\\xa0\\x80'
                    '%3D-%4D-%5D-Ni!?#\U0010FFFF\\xed\\xb3\\x8c'),
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(26) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, 'em')")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (but not matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`
            # * here `merge_surrogate_pairs` is ineffective, as
            #   both `url.b64` and `orig_b64` contain a non-UTF-8 and
            #   non-surrogate garbage -- namely, the `\xdd` byte just
            #   before the 'Ni!?' fragment -- which makes the binary
            #   contents undecodable with the `utf-8` codec, even with
            #   the `surrogatepass` error handler...
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-\xddNi!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELd1OaSE_I-2vv-2_v-2zjA=='),

                        # (`empty_path_slash`, `merge_surrogate_pairs`)
                        'norm_brief': 'em',
                    },
                },
            },
            expected_result=None,
        ).label(
        "(27) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(NOT matching, 'em', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized + coerced to `str`,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`
            # * here `merge_surrogate_pairs` is ineffective (as above),
            #   but that does not prevent matching because here `url.b64`
            #   and `orig_b64` contain same non-strict-UTF-8 bytes (i.e.,
            #   surrogates and non-surrogate garbage)
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELd1OaSE_I-2vv-2_v-2zjA=='),

                        # (`empty_path_slash`, `merge_surrogate_pairs`)
                        'norm_brief': 'em',
                    },
                },
            },
            expected_result={
                'url': (
                    # note: lack of the `unicode_str` option means that
                    # the result of normalization is a `bytes` object
                    # (which is then coerced to `str`, just for the
                    # "url" result item, by applying the helper function
                    # `as_str_with_minimum_esc()`; the bytes which encode
                    # surrogates, paired or unpaired, as well as any
                    # other non-strict-UTF-8 ones are escaped using
                    # the `\x...` notation)
                    'http://Ćma.example.com/?q=\\xed\\xb3\\x9d\\xed\\xa0\\x80'
                    '%3D-%4D-%5D-\\xddNi!?#\\xed\\xaf\\xbf\\xed\\xbf\\xbf\\xed\\xb3\\x8c'),
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(28) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, 'em', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (but not matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options: none
            # * here lack of `merge_surrogate_pairs` is irrelevant, as
            #   `url.b64` and `orig_b64` contain same non-strict-UTF-8
            #   bytes (i.e., surrogates and non-surrogate garbage)
            # * here lack of `empty_path_slash` causes that there is
            #   no match, as only `url.b64` has the URL's `path` empty
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELd1OaSE_I-2vv-2_v-2zjA=='),

                        # (no active normalization options)
                        'norm_brief': '',
                    },
                },
            },
            expected_result=None,
        ).label(
        "(29) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(NOT matching, '', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized + coerced to `str`,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options: none
            # * here lack of `merge_surrogate_pairs` is irrelevant, as
            #   `url.b64` and `orig_b64` contain same non-strict-UTF-8
            #   bytes (i.e., surrogates and non-surrogate garbage)
            # * here lack of `empty_path_slash` is irrelevant, as
            #   `orig_b64` and `url.b64` have the same URL path
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80/?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-\xddNi!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELd1OaSE_I-2vv-2_v-2zjA=='),

                        # (no active normalization options)
                        'norm_brief': '',
                    },
                },
            },
            expected_result={
                'url': (
                    # note: lack of the `unicode_str` option means that
                    # the result of normalization is a `bytes` object
                    # (which is then coerced to `str`, just for the
                    # "url" result item, by applying the helper function
                    # `as_str_with_minimum_esc()`; the bytes which encode
                    # surrogates, paired or unpaired, as well as any
                    # other non-strict-UTF-8 ones are escaped using
                    # the `\x...` notation)
                    'http://Ćma.example.com/?q=\\xed\\xb3\\x9d\\xed\\xa0\\x80'
                    '%3D-%4D-%5D-\\xddNi!?#\\xed\\xaf\\xbf\\xed\\xbf\\xbf\\xed\\xb3\\x8c'),
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(30) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, '', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (but not matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `unicode_str`
            # * here lack of `merge_surrogate_pairs` causes that there
            #   is no match
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELU5pIT8j7a-_7b-_7bOM'),

                        # (`empty_path_slash`, `unicode_str`)
                        'norm_brief': 'eu',
                    },
                },
            },
            expected_result=None,
        ).label(
        "(31) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(NOT matching, 'eu', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (but not matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match normalized `url.b64`
            #
            # -> result: nothing
            #
            # * normalization option set to true: `empty_path_slash`
            # * here lack of `merge_surrogate_pairs` causes that there
            #   is no match
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELU5pIT8j7a-_7b-_7bOM'),

                        # (`empty_path_slash`)
                        'norm_brief': 'e',
                    },
                },
            },
            expected_result=None,
        ).label(
        "(32) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(NOT matching, 'e', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (but not matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options:
            #   `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            # * here lack of `empty_path_slash` causes that there is
            #   no match, as only `url.b64` has the URL's `path` empty
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELU5pIT8j7a-_7b-_7bOM'),

                        # (`merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'mru',
                    },
                },
            },
            expected_result=None,
        ).label(
        "(33) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(NOT matching, 'mru', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (but not matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options:
            #   `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            # * here lack of `empty_path_slash` causes that there is
            #   no match, as only `orig_b64` has the URL's `path` empty
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80/?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006P3E97bOd'
                                     '7aCAJTNELSU0RC0lNUQtTmkhPyPtr7_tv7_ts4w='),

                        # (`merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'mru',
                    },
                },
            },
            expected_result=None,
        ).label(
        "(34) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(NOT matching, 'mru', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            # * here lack of `empty_path_slash` does not prevent matching,
            #   as both `orig_b64` and `url.b64` have the URL's `path` empty
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006P3E97bOd'
                                     '7aCAJTNELSU0RC0lNUQtTmkhPyPtr7_tv7_ts4w='),

                        # (`merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'mru',
                    },
                },
            },
            expected_result={
                'url': 'http://Ćma.example.com?q=\udcdd\ud800%3D-%4D-%5D-Ni!?#\U0010FFFF\udccc',
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(35) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, 'mru', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data`,
            # *and* `url.b64` in params (matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            # * here lack of `empty_path_slash` is irrelevant, as
            #   `orig_b64` and `url.b64` have the same URL path
            filtering_params={
                'url.b64': [
                    (b'HtTp://\xc4\x86ma.ExAmPlE.cOm:80/?q=\xed\xb3\x9d\xed\xa0\x80'
                     b'%3D-%4D-%5D-Ni!?#\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'url': 'SY:foo:cośtam/not-important',
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'htTP://\xc4\x86ma.eXample.COM:/?q=\xed\xb3\x9d\xed\xa0\x80'
                        #     b'%3D-%4D-%5D-Ni!?#\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHRUUDovL8SGbWEuZVhhbXBsZS5DT006Lz9xPe2z'
                                     'ne2ggCUzRC0lNEQtJTVELU5pIT8j7a-_7b-_7bOM'),

                        # (`merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'mru',
                    },
                },
            },
            expected_result={
                'url': 'http://Ćma.example.com/?q=\udcdd\ud800%3D-%4D-%5D-Ni!?#\U0010FFFF\udccc',
                'custom': {},  # (empty `custom` is harmless, as data spec removes it later anyway)
            },
        ).label(
        "(36) 'SY:'-prefixed `url`, `custom` with `url_data`, `url.b64` in params "
        "(matching, 'mru', ...)")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* `url.b64` in params (some matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        matches some of normalized `url.b64`
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized,
            #    unrelated data,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'url.b64': [
                    b'https://example.com/',
                    b'ftp://\xdd-non-UTF-8-garbage',
                    (b'HTTP://\xc4\x86ma.EXAMPLE.cOM:80/\xed\xb3\x9d\xed\xa0\x80'
                    b'Ala-ma-kota\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'),
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),

                        # (`empty_path_slash`, `merge_surrogate_pairs`,
                        #  `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'emru',
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': 'http://Ćma.example.com/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(37) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, `url.b64` in params "
        "(matching, 'emru')")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            #
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* `url.b64` in params (some matching!)
            # -- so: `url_orig` URL-safe-base64-decoded + normalized
            #        matches some of normalized `url.b64`
            #
            # -> result:
            #    `url` being `url_orig` URL-safe-base64-decoded + normalized,
            #    unrelated data,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'url.b64': [
                    b'https://example.com/',
                    b'ftp://\xdd-non-UTF-8-garbage',
                    (b'HTTP://\xc4\x86ma.EXAMPLE.cOM:80/\xed\xb3\x9d\xed\xa0\x80'
                     b'Ala-ma-kota\xed\xaf\xbf\xed\xbf\xbf\xed\xb3\x8c'),
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),

                        # (legacy flags, translated to: `unicode_str`, `merge_surrogate_pairs`,
                        #  `empty_path_slash`, `remove_ipv6_zone`)
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': 'http://Ćma.example.com/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(38) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, `url.b64` in params "
        "(matching, 'emru') [@legacy]")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* *no* `url.b64` in params (so it does not constraints us...)
            # -- so: there is *no* application-level matching/filtering
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + normalized,
            #    unrelated data,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'foobar': [
                    b'https://example.com/',
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),

                        # (`empty_path_slash`, `merge_surrogate_pairs`,
                        #  `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'emru',
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': 'http://Ćma.example.com/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(39) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data "
        "(matching, 'emru')")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            #
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* *no* `url.b64` in params (so it does not constraints us...)
            # -- so: there is *no* application-level matching/filtering
            #
            # -> result:
            #    `url` being `url_orig` URL-safe-base64-decoded + normalized,
            #    unrelated data,
            #    `custom` without `url_data`
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'foobar': [
                    b'https://example.com/',
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),

                        # (legacy flags, translated to: `unicode_str`, `merge_surrogate_pairs`,
                        #  `empty_path_slash`, `remove_ipv6_zone`)
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': 'http://Ćma.example.com/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(40) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data "
        "(matching, 'emru') [@legacy]")

        yield param(
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* `url.b64` in params (but none matching!)
            # -- so: `orig_b64` URL-safe-base64-decoded + normalized
            #        does *not* match any of normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'url.b64': [
                    b'https://example.com/',
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                    (b'http://\xc4\x86ma.eXample.COM:80/\xdd\xed\xa0\x80'
                     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),

                        # (`empty_path_slash`, `merge_surrogate_pairs`,
                        #  `remove_ipv6_zone`, `unicode_str`)
                        'norm_brief': 'emru',
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result=None,
        ).label(
        "(41) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, `url.b64` in params "
        "(NOT matching, 'emru')")

        yield param(
            # [analogous to previous case, but with `url_data` in legacy format]
            #
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* `url.b64` in params (but none matching!)
            # -- so: `url_orig` URL-safe-base64-decoded + normalized
            #        does *not* match any of normalized `url.b64`
            #
            # -> result: nothing
            #
            # remarks:
            # * active normalization options:
            #   `empty_path_slash`, `merge_surrogate_pairs`, `remove_ipv6_zone`, `unicode_str`
            filtering_params={
                'url.b64': [
                    b'https://example.com/',
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                    (b'http://\xc4\x86ma.eXample.COM:80/\xdd\xed\xa0\x80'
                     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),

                        # (legacy flags, translated to: `unicode_str`, `merge_surrogate_pairs`,
                        #  `empty_path_slash`, `remove_ipv6_zone`)
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result=None,
        ).label(
        "(42) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, `url.b64` in params "
        "(NOT matching, 'emru') [@legacy]")

        yield param(
            # [this example is not realistic -- yet it helps to test
            # URL-normalization-data-cache-related machinery...]
            #
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* *url_normalization_data_cache* containing some matching
            #       (fake) stuff (even though none of `url.b64` matches)
            # -- so: `orig_b64` URL-safe-base64-decoded + fake-normalizer-processed
            #    matches something...
            #
            # -> result:
            #    `url` being `orig_b64` URL-safe-base64-decoded + fake-normalizer-processed,
            #    unrelated data,
            #    `custom` without `url_data`
            filtering_params={
                'url.b64': [
                    b'https://example.com/',
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                ],
            },
            url_normalization_data_cache={
                'emru': (
                    # "cached" normalizer (here it is fake, of course):
                    lambda b: b.upper().decode('utf-8', 'replace'),

                    # "cached" normalized `url.b64` param values (here fake, of course):
                    [
                        ('HTTP://ĆMA.EXAMPLE.COM:80/\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd'
                         'ALA-MA-KOTA\U0010ffff\ufffd\ufffd\ufffd'),
                        'foo-bar-irrelevant-val',
                    ]
                ),
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'orig_b64': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                        'norm_brief': 'emru',
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': (
                    'HTTP://ĆMA.EXAMPLE.COM:80/\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd'
                    'ALA-MA-KOTA\U0010ffff\ufffd\ufffd\ufffd'),
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(43) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, "
        "faked normalization cache (matching, 'emru')")

        yield param(
            # [this example is not realistic -- yet it helps to test
            # URL-normalization-data-cache-related machinery...]
            #
            # [analogous to previous case, but with `url_data` in legacy format]
            #
            # 'SY:'-prefixed `url`,
            # `custom` with `url_data` + something else,
            # unrelated data,
            # *and* *url_normalization_data_cache* containing some matching
            #       (fake) stuff (even though none of `url.b64` matches)
            # -- so: `url_orig` URL-safe-base64-decoded + fake-normalizer-processed
            #    matches something...
            #
            # -> result:
            #    `url` being `url_orig` URL-safe-base64-decoded + fake-normalizer-processed,
            #    unrelated data,
            #    `custom` without `url_data`
            filtering_params={
                'url.b64': [
                    b'https://example.com/',
                    b'http://example.ORG:8080/?x=y&\xc4\x85=\xc4\x99',
                ],
            },
            url_normalization_data_cache={
                'emru': (
                    # "cached" normalizer (here it is fake, of course):
                    lambda b: b.upper().decode('utf-8', 'replace'),

                    # "cached" normalized `url.b64` param values (here fake, of course):
                    [
                        ('HTTP://ĆMA.EXAMPLE.COM:80/\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd'
                         'ALA-MA-KOTA\U0010ffff\ufffd\ufffd\ufffd'),
                        'foo-bar-irrelevant-val',
                    ]
                ),
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': ('aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': (
                    'HTTP://ĆMA.EXAMPLE.COM:80/\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd'
                    'ALA-MA-KOTA\U0010ffff\ufffd\ufffd\ufffd'),
                'unrelated-data': 'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(44) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, "
        "faked normalization cache (matching, 'emru') [@legacy]")

        yield param(
            # [this example is not realistic -- yet it helps to test
            # URL-normalization-data-cache-related machinery...]
            #
            # similar situation but even *without* the `url.b64` params (but
            # that does not matter, as what is important is the cache!)
            url_normalization_data_cache={
                'emru': (
                    # "cached" normalizer (here it is fake, of course):
                    lambda b: b.title().decode('utf-8'),
                    # "cached" normalized `url.b64` param values (here fake, of course):
                    [
                        'Https://Example.Com:',
                    ]
                ),
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `orig_b64` is URL-safe-base64-encoded: b`https://example.com:`
                        'orig_b64': ('aHR0cHM6Ly9leGFtcGxlLmNvbTo='),
                        'norm_brief': 'emru',
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': b'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': 'Https://Example.Com:',
                'unrelated-data': b'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(45) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, "
        "faked normalization cache (matching, 'emru')")

        yield param(
            # [this example is not realistic -- yet it helps to test
            # URL-normalization-data-cache-related machinery...]
            #
            # [analogous to previous case, but with `url_data` in legacy format]
            url_normalization_data_cache={
                'emru': (
                    # "cached" normalizer (here it is fake, of course):
                    lambda b: b.title().decode('utf-8'),
                    # "cached" normalized `url.b64` param values (here fake, of course):
                    [
                        'Https://Example.Com:',
                    ]
                ),
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded: b`https://example.com:`
                        'url_orig': ('aHR0cHM6Ly9leGFtcGxlLmNvbTo='),
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'something_else': 123,
                },
                'url': 'SY:foo:cośtam/not-important',
                'unrelated-data': b'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'something_else': 123,
                },
                'url': 'Https://Example.Com:',
                'unrelated-data': b'FOO BAR !@#$%^&*()',
            },
        ).label(
        "(46) 'SY:'-prefixed `url`, `custom` with `url_data`, unrelated data, "
        "faked normalization cache (matching, 'emru') [@legacy]")

    @foreach(cases)
    def test(self, raw_result_dict, expected_result, expected_log_regexes=(),
             filtering_params=None,
             url_normalization_data_cache=None):
        raw_result_dict = copy.deepcopy(raw_result_dict)
        mock = MagicMock()
        meth = MethodProxy(_EventsQueryProcessor, mock, class_attrs='_call_silencing_decode_err')
        mock._filtering_params = (
            copy.deepcopy(filtering_params)
            if filtering_params is not None
            else {})
        mock._url_normalization_data_cache = (
            url_normalization_data_cache
            if url_normalization_data_cache is not None
            else {})
        with self.assertLogRegexes(module_logger, expected_log_regexes):

            actual_result = meth._preprocess_result_dict(raw_result_dict)

        self.assertEqualIncludingTypes(actual_result, expected_result)

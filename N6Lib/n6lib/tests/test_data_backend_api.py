# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import unittest
from datetime import datetime as dt

from mock import (
    MagicMock,
    patch,
    sentinel as sen,
)
from sqlalchemy import and_
from unittest_expander import expand, foreach, param

from n6lib.data_backend_api import _QueryProcessor
from n6lib.data_spec import N6DataSpec, N6InsideDataSpec
from n6lib.sqlalchemy_related_test_helpers import sqlalchemy_expr_to_str
from n6lib.unit_test_helpers import MethodProxy


## TODO: N6DataBackendAPI tests
## TODO: more _QueryProcessor tests (__init__ etc.)


@expand
class Test_QueryProcessor___get_key_to_query_func(unittest.TestCase):

    @foreach(
        param(data_spec_class=N6DataSpec),
        param(data_spec_class=N6InsideDataSpec),
    )
    def test(self, data_spec_class):
        cls = _QueryProcessor
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
            'source': key_query,
            'sport': key_query,
            'status': key_query,
            'target': key_query,
            'url': key_query,
            'url.sub': qmc_mock.like_query,
        })


class Test_QueryProcessor__delete_opt_prefixed_params(unittest.TestCase):

    def test(self):
        mock = MagicMock()
        meth = MethodProxy(_QueryProcessor, mock)
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
        meth.delete_opt_prefixed_params(params)
        self.assertEqual(params, expected_params)
        self.assertEqual(mock.mock_calls, [])


@expand
class Test_QueryProcessor__generate_query_results(unittest.TestCase):

    _UTCNOW = dt(2015, 1, 3, 17, 18, 19)

    # a helper that makes the expression query reprs for a given time window
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
            given_params={
                'time.min': [dt(2015, 1, 3, 16, 17, 18)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-03 16:17:18',
            ),
        ).label('no time.max/until given, 1 window'),

        param(
            given_params={
                'time.max': [dt(2015, 1, 5, 14, 15, 16)],
                'time.min': [dt(2015, 1, 4, 16, 17, 18)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-05 14:15:16',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.max given, 1 window'),

        param(
            given_params={
                'time.until': [dt(2015, 1, 5, 14, 15, 16, 999999)],
                'time.min': [dt(2015, 1, 4, 16, 17, 18)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-05 14:15:16.999999',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.until given, 1 window'),

        param(
            given_params={
                'time.min': [dt(2015, 1, 2, 16, 17, 18)],
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
            given_params={
                'time.max': [dt(2015, 1, 5, 14, 15, 16)],
                'time.min': [dt(2015, 1, 2, 16, 17, 18, 1)],
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
            given_params={
                'time.until': [dt(2015, 1, 2, 14, 15, 16)],
                'time.min': [dt(2014, 12, 30, 16, 17, 18)],
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
            given_params={
                'time.min': [dt(2015, 1, 2, 18, 18, 19)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-02 18:18:19',
            ),
        ).label('no time.max/until given, 1 window, delta == window'),

        param(
            given_params={
                'time.max': [dt(2015, 1, 5, 16, 17, 18)],
                'time.min': [dt(2015, 1, 4, 16, 17, 18)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-05 16:17:18',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.max given, 1 window, delta == window'),

        param(
            given_params={
                'time.until': [dt(2015, 1, 5)],
                'time.min': [dt(2015, 1, 4)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<',
                upper='2015-01-05 00:00:00',
                lower='2015-01-04 00:00:00',
            ),
        ).label('time.until given, 1 window, delta == window'),

        param(
            given_params={
                'time.min': [dt(2015, 1, 1, 18, 18, 19)],
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
            given_params={
                'time.max': [dt(2015, 1, 2, 14, 15, 16, 999999)],
                'time.min': [dt(2014, 12, 30, 14, 15, 16, 999999)],
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
            given_params={
                'time.until': [dt(2015, 1, 5)],
                'time.min': [dt(2015, 1, 2)],
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
            given_params={
                'time.min': [dt(2015, 1, 3, 18, 18, 19)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-03 18:18:19',
            ),
        ).label('time_min == utcnow() + 1h, no time.max/until given'),

        param(
            given_params={
                'time.max': [dt(2015, 1, 4, 16, 17, 18)],
                'time.min': [dt(2015, 1, 4, 16, 17, 18)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-04 16:17:18',
                lower='2015-01-04 16:17:18',
            ),
        ).label('time.min == time.max'),

        param(
            given_params={
                'time.until': [dt(2015, 1, 4, 16, 17, 18, 999999)],
                'time.min': [dt(2015, 1, 4, 16, 17, 18, 999999)],
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
            given_params={
                'time.min': [dt(2015, 1, 3, 18, 18, 19, 1)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-03 18:18:19',  # utcnow() + 1h
                lower='2015-01-03 18:18:19.000001',
            ),
        ).label('time_min > utcnow() + 1h, no time.max/until given'),

        param(
            given_params={
                'time.max': [dt(2015, 1, 4, 16, 17, 18)],
                'time.min': [dt(2015, 1, 7, 18, 19, 20)],
            },
            expected_query_expr_reprs=_win(
                upper_op='<=',
                upper='2015-01-04 16:17:18',
                lower='2015-01-07 18:19:20',
            ),
        ).label('time.min > time.max'),

        param(
            given_params={
                'time.until': [dt(2015, 1, 4, 16, 17, 18)],
                'time.min': [dt(2015, 1, 5, 16, 17, 18)],
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
                                                          given_params,
                                                          expected_query_expr_reprs):
        mock = MagicMock()
        meth = MethodProxy(
            _QueryProcessor,
            mock,
            class_attrs=[
                # for them, the actual members/methods (not mocks) will be used
                # class constants:
                'queried_model_class',
                'client_relationship',
                'client_asoc_model_class',
                # methods:
                'pop_time_min_max_until',
                'pop_limit',
                'make_time_cmp_generator',
                'query__ordering_by',
                'query__limit',
            ])
        actual_query_expr_reprs = []
        and_mock = self._make_the_and_mock(actual_query_expr_reprs)
        query_mock = self._make_the_query_mock(actual_query_expr_reprs)
        mock.build_query.return_value = query_mock
        with patch('n6lib.data_backend_api.and_', and_mock), \
             patch('n6lib.data_backend_api.utcnow', return_value=self._UTCNOW):
            list(meth.generate_query_results(
                given_params,
                item_number_limit=None,
                day_step=1))
        self.assertEqual(actual_query_expr_reprs, expected_query_expr_reprs)


    def _make_the_and_mock(self, actual_query_expr_reprs):
        def and_mock_side_effect(*sqlalchemy_conds):
            cond = and_(*sqlalchemy_conds)
            cond_str = sqlalchemy_expr_to_str(cond)
            actual_query_expr_reprs.append(cond_str)
            return sen.and_
        and_mock = MagicMock()
        and_mock.side_effect = and_mock_side_effect
        return and_mock


    def _make_the_query_mock(self, actual_query_expr_reprs):
        def query_mock_order_by_side_effect(sqlalchemy_expr):
            expr_str = sqlalchemy_expr_to_str(sqlalchemy_expr)
            actual_query_expr_reprs.append(expr_str)
            return query_mock
        query_mock = MagicMock()
        query_mock.order_by.side_effect = query_mock_order_by_side_effect
        query_mock.filter.return_value = query_mock
        query_mock.outerjoin.return_value = query_mock
        query_mock.options.return_value = query_mock
        return query_mock


    ## TODO: test other aspects of the generate_query_results() method...

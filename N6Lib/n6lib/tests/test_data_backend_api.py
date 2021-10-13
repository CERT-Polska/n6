# Copyright (c) 2013-2021 NASK. All rights reserved.

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
class Test_EventsQueryProcessor___get_key_to_query_func(unittest.TestCase):

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
class Test_EventsQueryProcessor__generate_query_results(unittest.TestCase):

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
            raw_result_dict={
                # 'SY:'-prefixed `url`, no `custom`/`url_data`, some data
                # -> nothing
                'url': u'SY:cośtam',
                'foo': u'bar',
            },
            expected_result=None,
        )
        yield param(
            raw_result_dict={
                # 'SY:'-prefixed `url`, `custom` without `url_data`, some data
                # -> nothing
                'custom': {'spam': 'ham'},
                'url': u'SY:cośtam',
                'foo': 'bar',
            },
            expected_result=None,
        )
        yield param(
            # `custom`+`url_data`, no 'url'
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': {
                       'url_orig': 'x',
                       'url_norm_opts': {'x': 'y'},
                   },
               },
            },
            expected_result=None,
        )
        yield param(
            # `custom`+`url_data`, some data, no 'url'
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': {
                       'url_orig': u'x',
                       'url_norm_opts': {'x': u'y'},
                   },
               },
               'foo': u'bar',
            },
            expected_result=None,
        )
        yield param(
            # `url` without 'SY:' prefix, `custom`+`url_data`
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': {
                       'url_orig': u'x',
                       'url_norm_opts': {'x': u'y'},
                   },
               },
               'url': u'foo:bar',
            },
            expected_result=None,
        )
        yield param(
            # `url` without 'SY:' prefix, `custom`+`url_data`, some data
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': {
                       'url_orig': 'x',
                       'url_norm_opts': {'x': 'y'},
                   },
               },
               'foo': 'bar',
            },
            expected_result=None,
        )
        yield param(
            # `custom`+`url_data` but the latter is not valid (not a dict)
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': [u'something'],
               },
               'url': u'SY:foo:bar',
            },
            expected_result=None,
        )
        yield param(
            # `custom`+`url_data` but the latter is not valid (missing keys)
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': {
                       'url_norm_opts': {'x': 'y'},
                   },
               },
               'foo': 'bar',
            },
            expected_result=None,
        )
        yield param(
            # `custom`+`url_data` but the latter is not valid (illegal keys)
            # -> nothing
            raw_result_dict={
               'custom': {
                   'url_data': {
                       'url_orig': u'x',
                       'url_norm_opts': {'x': 'y'},
                       'spam': 'ham',
                   },
               },
               'foo': 'bar',
            },
            expected_result=None,
        )
        yield param(
            # some data. no `url`, no `url_data`
            # -> some data
            raw_result_dict={
               'foo': 'bar',
            },
            expected_result={
               'foo': 'bar',
            },
        )
        yield param(
            # some data, no `url`, `custom` without `url_data`
            # -> some data, `custom`
            raw_result_dict={
               'custom': {'spam': u'ham'},
               'foo': u'bar',
            },
            expected_result={
                'custom': {'spam': u'ham'},
               'foo': u'bar',
            },
        )
        yield param(
            # `url` without 'SY:' prefix, some data, no `custom`/`url_data`
            # -> `url`, some data
            raw_result_dict={
               'url': u'something-else',
               'foo': u'bar',
            },
            expected_result={
               'url': u'something-else',
               'foo': u'bar',
            },
        )
        yield param(
            # `url` without 'SY:' prefix, some data, `custom` without `url_data`
            # -> `url`, some data, `custom`
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
        )
        yield param(
            # `url`, `custom`+`url_data`+other, some data
            # *and* `url.b64` in params (some matching!)
            # -- so: app-level matching: normalized `url_orig` matched some of `url.b64`
            # -> `url` being normalized `url_orig`, some data, custom without `url_data`
            filtering_params={
                'url.b64': [
                    u'https://example.com/',
                    u'HTTP://Ćma.EXAMPLE.cOM:80/\udcdd\ud800Ala-ma-kota\udbff\udfff\udccc',
                    u'http://example.ORG:8080/?x=y&ą=ę',
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': (u'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     u'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'spam': 123,
                },
                'url': u'SY:foo:bar/not-important',
                'some-data': u'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'spam': 123,
                },
                'url': u'http://Ćma.example.com/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc',
                'some-data': u'FOO BAR !@#$%^&*()',
            },
        )
        yield param(
            # `url`, `custom`+`url_data`+other, some data
            # *and* *no* `url.b64` in params (so it does not constraints us...)
            # -- so: *no* app-level matching
            # -> `url` being normalized `url_orig`, some data, custom without `url_data`
            filtering_params={
                'foobar': [
                    u'https://example.com/',
                    u'http://example.ORG:8080/?x=y&ą=ę',
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
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'spam': 123,
                },
                'url': 'SY:foo:bar/not-important',
                'some-data': 'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'spam': 123,
                },
                'url': u'http://Ćma.example.com/\udcdd\ud800Ala-ma-kota\U0010FFFF\udccc',
                'some-data': 'FOO BAR !@#$%^&*()',
            },
        )
        yield param(
            # `url`, `custom`+`url_data`+other, some data
            # *and* `url.b64` in params (but none matching!)
            # -- so: app-level matching: normalized `url_orig` did *not* matched any of `url.b64`
            # -> nothing
            filtering_params={
                'url.b64': [
                    u'https://example.com/',
                    u'http://example.ORG:8080/?x=y&ą=ę',
                ],
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': (u'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     u'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'spam': 123,
                },
                'url': u'SY:foo:bar/not-important',
                'some-data': u'FOO BAR !@#$%^&*()',
            },
            expected_result=None,
        )
        yield param(
            # `url`, `custom`+`url_data`+other, some data
            # *and* (although none of `url.b64` matches in params) *url_normalization_data_cache*
            # containing some matching (fake) stuff...
            # -- so: app-level matching: fake-normalizer-processed `url_orig` matched something...
            # -> `url` being fake-normalizer-processed `url_orig`, etc. ...
            filtering_params={
                'url.b64': [
                    u'https://example.com/',
                    u'http://example.ORG:8080/?x=y&ą=ę',
                ],
            },
            url_normalization_data_cache={
                (('epslash', True), ('rmzone', True), ('transcode1st', True)): (
                    # "cached" normalizer (here it is fake, of course):
                    bytes.upper,

                    # "cached" normalized `url.b64` param values (here fake, of course):
                    [
                        b'HTTP://\xc4\x86MA.EXAMPLE.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        b'ALA-MA-KOTA\xf4\x8f\xbf\xbf\xed\xb3\x8c',
                    ]
                ),
            },
            raw_result_dict={
                'custom': {
                    'url_data': {
                        # `url_orig` is URL-safe-base64-encoded:
                        #     b'http://\xc4\x86ma.eXample.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        #     b'Ala-ma-kota\xf4\x8f\xbf\xbf\xed\xb3\x8c'
                        'url_orig': (u'aHR0cDovL8SGbWEuZVhhbXBsZS5DT006OD'
                                     u'Av7bOd7aCAQWxhLW1hLWtvdGH0j7-_7bOM'),
                        'url_norm_opts': {'transcode1st': True, 'epslash': True, 'rmzone': True},
                    },
                    'spam': 123,
                },
                'url': u'SY:foo:bar/not-important',
                'some-data': u'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'spam': 123,
                },
                # note: still bytes because of the above fake normalizer (`bytes.upper`)...
                'url': (b'HTTP://\xc4\x86MA.EXAMPLE.COM:80/\xed\xb3\x9d\xed\xa0\x80'
                        b'ALA-MA-KOTA\xf4\x8f\xbf\xbf\xed\xb3\x8c'),
                'some-data': u'FOO BAR !@#$%^&*()',
            },
        )
        yield param(
            # similar situation but even *without* the `url.b64` params (but
            # that does not matter, as what is important is the cache!)
            url_normalization_data_cache={
                (('epslash', True), ('rmzone', True), ('transcode1st', True)): (
                    # "cached" normalizer (here it is fake, of course):
                    lambda b: b.upper().decode('utf-8'),
                    # "cached" normalized `url.b64` param values (here fake, of course):
                    [
                        u'HTTPS://EXAMPLE.COM:',
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
                    'spam': 123,
                },
                'url': 'SY:foo:bar/not-important',
                'some-data': b'FOO BAR !@#$%^&*()',
            },
            expected_result={
                'custom': {
                    'spam': 123,
                },
                'url': u'HTTPS://EXAMPLE.COM:',
                'some-data': b'FOO BAR !@#$%^&*()',
            },
        )

    @foreach(cases)
    def test(self, raw_result_dict, expected_result,
             filtering_params=None,
             url_normalization_data_cache=None):
        mock = MagicMock()
        meth = MethodProxy(_EventsQueryProcessor, mock)
        mock._filtering_params = (
            copy.deepcopy(filtering_params)
            if filtering_params is not None
            else {})
        mock._url_normalization_data_cache = (
            url_normalization_data_cache
            if url_normalization_data_cache is not None
            else {})
        raw_result_dict = copy.deepcopy(raw_result_dict)
        actual_result = meth._preprocess_result_dict(raw_result_dict)
        self.assertEqualIncludingTypes(actual_result, expected_result)

# Copyright (c) 2013-2025 NASK. All rights reserved.

import unittest
from unittest.mock import (
    ANY,
    call,
    MagicMock,
    patch,
    sentinel as sen,
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPForbidden,
    HTTPNotFound,
    HTTPInternalServerError,
)

from n6sdk.exceptions import (
    DataAPIError,
    DataLookupError,
    AuthorizationError,
    DataFromClientError,
    ParamCleaningError,
    ResultCleaningError,
)
from n6sdk.pyramid_commons import (
    AbstractViewBase,
    DefaultStreamViewBase,
    ConfigHelper,
    exc_to_http_exc,
)


class Test_get_default_http_methods(unittest.TestCase):

    def test_for_AbstractViewBase(self):
        self.assertEqual(
            AbstractViewBase.get_default_http_methods(),
            'GET')

    def test_for_DefaultStreamViewBase(self):
        self.assertEqual(
            DefaultStreamViewBase.get_default_http_methods(),
            'GET')


class TestDefaultStreamViewBase_validate_url_pattern(unittest.TestCase):

    prefix = '/some-url-path/incidents'

    def _test_error(self, url_pattern):
        with self.assertRaises(HTTPInternalServerError):
            DefaultStreamViewBase.validate_url_pattern(url_pattern)

    def test_ok(self):
        url_pattern = self.prefix + '.{renderer}'
        none = DefaultStreamViewBase.validate_url_pattern(url_pattern)
        self.assertIsNone(none)

    def test_error_1(self):
        url_pattern = self.prefix + '{renderer}'
        self._test_error(url_pattern)

    def test_error_2(self):
        url_pattern = self.prefix + '.{foo}'
        self._test_error(url_pattern)

    def test_error_3(self):
        url_pattern = self.prefix + '.foo'
        self._test_error(url_pattern)

    def test_error_4(self):
        url_pattern = self.prefix + '.{renderer}.foo'
        self._test_error(url_pattern)


@patch('n6sdk.pyramid_commons._pyramid_commons.registered_stream_renderers',
       new={'some': MagicMock(), 'another': MagicMock()})
class TestDefaultStreamViewBase_concrete_view_class(unittest.TestCase):

    _KWARGS_BASE = dict(
        resource_id='/some/resource.id',
        pyramid_configurator=sen.configurator,
        data_spec=sen.data_spec,
        data_backend_api_method='some_method_name',
        renderers=('some',),
    )

    def _basic_asserts(self, result):
        self.assertTrue(issubclass(result, DefaultStreamViewBase))
        self.assertIsNot(result, DefaultStreamViewBase)
        self.assertEqual(
            result.__name__,
            '_{base_class_name}_subclass_for_some_resource_id'.format(
                base_class_name=result.__mro__[1].__name__))
        self.assertEqual(
           result.__qualname__,
           'AbstractViewBase.concrete_view_class.<locals>.'
           '_{base_class_name}_subclass_for_some_resource_id'.format(
               base_class_name=result.__mro__[1].__name__))
        self.assertEqual(result.resource_id, '/some/resource.id')
        self.assertIs(result.data_spec, sen.data_spec)
        self.assertEqual(result.data_backend_api_method, 'some_method_name')
        self.assertEqual(result.renderers, {'some'})
        self.assertIs(result.adjust_exc, DefaultStreamViewBase.adjust_exc)

    def test_with_renderers_as_str(self, *args):
        result = DefaultStreamViewBase.concrete_view_class(**dict(
            self._KWARGS_BASE,
            renderers='some'))
        self._basic_asserts(result)

    def test_with_renderers_as_iterable_of_str(self, *args):
        result = DefaultStreamViewBase.concrete_view_class(**self._KWARGS_BASE)
        self._basic_asserts(result)

    def test_for_subclass(self, *args):
        class SomeViewBase(DefaultStreamViewBase):
            x = 42
        result = SomeViewBase.concrete_view_class(**self._KWARGS_BASE)
        self._basic_asserts(result)
        self.assertTrue(issubclass(result, SomeViewBase))
        self.assertEqual(result.x, 42)

    def test_unregistered_renderer_error(self):
        with self.assertRaisesRegex(ValueError, r'renderer.*not.*registered'):
            DefaultStreamViewBase.concrete_view_class(**dict(
                self._KWARGS_BASE,
                renderers=['some_unregistered']))


class TestDefaultStreamViewBase_iter_deduplicated_params(unittest.TestCase):

    def test(self):
        func = DefaultStreamViewBase.iter_deduplicated_params
        self.assertIs(func, AbstractViewBase.iter_deduplicated_params)

        obj = MagicMock()
        obj.__class__ = DefaultStreamViewBase
        obj.params_only_from_body = DefaultStreamViewBase.params_only_from_body
        obj.comma_separated_only_for = DefaultStreamViewBase.comma_separated_only_for

        obj.request.params.__iter__.return_value = iter(['foo', 'bar', 'spam'])
        obj.request.params.getall.side_effect = {'foo': ['f1'],
                                                 'bar': ['b1,b2,b3'],
                                                 'spam': ['s1', 's2,s3']}.__getitem__

        _get_par = DefaultStreamViewBase.get_params_from_request
        obj.get_params_from_request.side_effect = lambda: _get_par(obj)

        _preproc = DefaultStreamViewBase.preprocess_param_values
        obj.preprocess_param_values.side_effect = lambda key, val: _preproc(obj, key, val)

        _iter_val = DefaultStreamViewBase.iter_values_from_param_value
        obj.iter_values_from_param_value.side_effect = lambda key, val: _iter_val(obj, key, val)

        result = list(func(obj))

        self.assertEqual(obj.get_params_from_request.mock_calls, [
            call(),
        ])
        self.assertEqual(obj.request.params.__iter__.mock_calls, [
            call(),
        ])
        self.assertEqual(obj.request.params.getall.mock_calls, [
            call('foo'),
            call('bar'),
            call('spam'),
        ])
        self.assertEqual(obj.preprocess_param_values.mock_calls, [
            call('foo', ['f1']),
            call('bar', ['b1,b2,b3']),
            call('spam', ['s1', 's2,s3']),
        ])
        self.assertEqual(obj.iter_values_from_param_value.mock_calls, [
            call('foo', 'f1'),
            call('bar', 'b1,b2,b3'),
            call('spam', 's1'),
            call('spam', 's2,s3'),
        ])
        self.assertEqual(result, [
            ('foo', ['f1']),
            ('bar', ['b1', 'b2', 'b3']),
            ('spam', ['s1', 's2', 's3']),
        ])


class TestDefaultStreamViewBase_call_api(unittest.TestCase):

    class SomeAdjustedExc(Exception):
        def __init__(self, given_exc):
            self.given_exc = given_exc  # (only for introspection in the tests)

    def setUp(self):
        self.data_spec = MagicMock()
        self.data_spec.clean_result_dict.side_effect = self.cleaned_list = [
            sen.cleaned_result_dict_1,
            sen.cleaned_result_dict_2,
            sen.cleaned_result_dict_3,
        ]

        SomeAdjustedExc = self.SomeAdjustedExc
        patcher = patch(
            'n6sdk.pyramid_commons._pyramid_commons.DefaultStreamViewBase.adjust_exc',
            side_effect=(lambda exc: SomeAdjustedExc(exc)))
        self.adjust_exc = patcher.start()
        self.addCleanup(patcher.stop)

        self.request = MagicMock()
        self.request.registry.data_backend_api.my_api_method = (
            sen.api_method)

        with patch('n6sdk.pyramid_commons._pyramid_commons.registered_stream_renderers',
                   new={'some': MagicMock()}):
            self.cls = DefaultStreamViewBase.concrete_view_class(
                resource_id='/some/resource.id',
                pyramid_configurator=sen.configurator,
                renderers=frozenset({'some'}),
                data_spec=self.data_spec,
                data_backend_api_method='my_api_method')

        self.cls._get_renderer_name = (lambda self: 'some')
        self.cls.call_api_method = MagicMock()
        self.cls.call_api_method.return_value = self._fake_backend_iter()

        # To be set in `_fake_backend_iter()`:
        self.backend_iter_finished = None

        # To be set in `_do_call()`:
        self.results = None
        self.not_produced_at_all = None

        self.cls.get_clean_result_dict_kwargs = MagicMock(
            return_value={'kwarg': sen.kwarg})

        self.obj = self.cls(sen.context, self.request)

        self.postprocessed_cleaned_results = []
        self.obj.postprocess_cleaned_result = self.postprocessed_cleaned_results.append

    def _fake_backend_iter(self):
        max_num_of = len(self.not_produced_at_all)
        assert max_num_of == 3, 'internal test assumption'
        self.backend_iter_finished = False
        try:
            for _ in range(max_num_of):
                result_dict = self.not_produced_at_all.pop(0)
                yield result_dict
        finally:
            self.backend_iter_finished = True

    def _do_call(self):
        self.results = []
        self.not_produced_at_all = [
            sen.result_dict_1,
            sen.result_dict_2,
            sen.result_dict_3,
        ]
        call_api_iterator = self.obj.call_api()
        while True:
            try:
                self.results.append(next(call_api_iterator))
            except StopIteration:
                break

    def _test_exc_in_the_middle(self, exc_class, flag=None,
                                expected_exc_adjust=True):
        self.cleaned_list[1] = exc_class
        self.assertTrue(self.cls.break_on_result_cleaning_error)
        if flag is not None:
            self.cls.break_on_result_cleaning_error = flag
        if expected_exc_adjust:
            with self.assertRaises(self.SomeAdjustedExc) as cm:
                self._do_call()
            self.assertIsInstance(cm.exception.given_exc, exc_class)
            self.assertEqual(self.adjust_exc.call_count, 1)
        else:
            with self.assertRaises(exc_class):
                self._do_call()
            self.assertEqual(self.adjust_exc.call_count, 0)
        self.assertTrue(self.backend_iter_finished)
        self.cls.get_clean_result_dict_kwargs.assert_called_once_with()
        self.cls.call_api_method.assert_called_once_with(sen.api_method)
        self.assertEqual(self.data_spec.clean_result_dict.mock_calls, [
            call(sen.result_dict_1, kwarg=sen.kwarg),
            call(sen.result_dict_2, kwarg=sen.kwarg),
        ])
        self.assertEqual(self.results, [
            sen.cleaned_result_dict_1,
        ])
        self.assertEqual(self.results, self.postprocessed_cleaned_results)
        self.assertEqual(self.not_produced_at_all, [
            sen.result_dict_3,
        ])

    def test_full_success(self):
        self._do_call()
        self.assertTrue(self.backend_iter_finished)
        self.assertEqual(self.adjust_exc.call_count, 0)
        self.cls.get_clean_result_dict_kwargs.assert_called_once_with()
        self.cls.call_api_method.assert_called_once_with(sen.api_method)
        self.assertEqual(self.data_spec.clean_result_dict.mock_calls, [
            call(sen.result_dict_1, kwarg=sen.kwarg),
            call(sen.result_dict_2, kwarg=sen.kwarg),
            call(sen.result_dict_3, kwarg=sen.kwarg),
        ])
        self.assertEqual(self.results, [
            sen.cleaned_result_dict_1,
            sen.cleaned_result_dict_2,
            sen.cleaned_result_dict_3,
        ])
        self.assertEqual(self.results, self.postprocessed_cleaned_results)

    def test_skipping_result_when_it_is_None(self):
        self.cleaned_list[1] = None
        self._do_call()
        self.assertTrue(self.backend_iter_finished)
        self.assertEqual(self.adjust_exc.call_count, 0)
        self.cls.get_clean_result_dict_kwargs.assert_called_once_with()
        self.cls.call_api_method.assert_called_once_with(sen.api_method)
        self.assertEqual(self.data_spec.clean_result_dict.mock_calls, [
            call(sen.result_dict_1, kwarg=sen.kwarg),
            call(sen.result_dict_2, kwarg=sen.kwarg),
            call(sen.result_dict_3, kwarg=sen.kwarg),
        ])
        self.assertEqual(self.results, [
            sen.cleaned_result_dict_1,
            sen.cleaned_result_dict_3,
        ])
        self.assertEqual(self.results, self.postprocessed_cleaned_results)

    def test_breaking_on_Exception(self):
        self.cls.call_api_method.side_effect = Exception
        with self.assertRaises(self.SomeAdjustedExc) as cm:
            self._do_call()
        self.assertIsInstance(cm.exception.given_exc, Exception)
        self.assertIsNone(self.backend_iter_finished)  # (<- not even started)
        self.assertEqual(self.adjust_exc.call_count, 1)
        self.cls.get_clean_result_dict_kwargs.assert_called_once_with()
        self.cls.call_api_method.assert_called_once_with(sen.api_method)
        self.assertEqual(self.data_spec.clean_result_dict.call_count, 0)
        self.assertEqual(self.results, [])
        self.assertEqual(self.results, self.postprocessed_cleaned_results)
        self.assertEqual(self.not_produced_at_all, [
            sen.result_dict_1,
            sen.result_dict_2,
            sen.result_dict_3,
        ])

    def test_breaking_on_ResultCleaningError_if_flag_is_true(self):
        self._test_exc_in_the_middle(ResultCleaningError)

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_skipping_ResultCleaningError_if_flag_is_false(self, LOGGER):
        self.cleaned_list[1] = ResultCleaningError
        self.cls.break_on_result_cleaning_error = False
        self._do_call()
        self.assertTrue(self.backend_iter_finished)
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, ANY),
        ])
        self.assertEqual(self.adjust_exc.call_count, 0)
        self.cls.get_clean_result_dict_kwargs.assert_called_once_with()
        self.cls.call_api_method.assert_called_once_with(sen.api_method)
        self.assertEqual(self.data_spec.clean_result_dict.mock_calls, [
            call(sen.result_dict_1, kwarg=sen.kwarg),
            call(sen.result_dict_2, kwarg=sen.kwarg),
            call(sen.result_dict_3, kwarg=sen.kwarg),
        ])
        self.assertEqual(self.results, [
            sen.cleaned_result_dict_1,
            sen.cleaned_result_dict_3,
        ])
        self.assertEqual(self.results, self.postprocessed_cleaned_results)

    def test_breaking_on_another_Exception_if_flag_is_true(self):
        self._test_exc_in_the_middle(ZeroDivisionError)

    def test_breaking_on_another_Exception_if_flag_is_false(self):
        self._test_exc_in_the_middle(ZeroDivisionError, flag=False)

    def test_breaking_on_non_Exception_if_flag_is_true(self):
        self._test_exc_in_the_middle(BaseException,
                                     expected_exc_adjust=False)

    def test_breaking_on_non_Exception_if_flag_is_false(self):
        self._test_exc_in_the_middle(BaseException, flag=False,
                                     expected_exc_adjust=False)


## TODO:
# class TestDefaultStreamViewBase__...
# class TestDefaultStreamViewBase__...
# class TestDefaultStreamViewBase__...
# class Test...
# class Test...
# class Test...


class TestConfigHelper(unittest.TestCase):

    ## TODO:
    # def test...
    # def test...
    # def test...

    @patch('n6sdk.pyramid_commons._pyramid_commons.exc_to_http_exc')
    def test_exception_view(self, exc_to_http_exc_mock):
        http_exc = HTTPNotFound('FOO')
        exc_to_http_exc_mock.return_value = http_exc
        assert http_exc.code == 404
        assert http_exc.content_type == 'text/html'
        assert http_exc.body == b''
        request = MagicMock()
        request.environ = {'HTTP_ACCEPT': 'text/html'}
        result = ConfigHelper.exception_view(sen.exc, request)
        self.assertIs(result, http_exc)
        self.assertEqual(http_exc.content_type, 'text/plain')  # no HTML
        self.assertNotIn(b'<', http_exc.body)                  # no HTML
        self.assertIn(b'404', http_exc.body)
        self.assertIn(b'FOO', http_exc.body)
        self.assertEqual(exc_to_http_exc_mock.mock_calls, [
            call(sen.exc),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.exc_to_http_exc')
    def test_exception_view__http_exc_body_already_set(self, exc_to_http_exc_mock):
        http_exc = HTTPNotFound('FOO', body=b'SPAM', content_type='text/spam')
        exc_to_http_exc_mock.return_value = http_exc
        assert http_exc.code == 404
        assert http_exc.content_type == 'text/spam'
        assert http_exc.body == b'SPAM'
        request = MagicMock()
        request.environ = {'HTTP_ACCEPT': 'text/html'}
        result = ConfigHelper.exception_view(sen.exc, request)
        self.assertIs(result, http_exc)
        self.assertEqual(http_exc.content_type, 'text/spam')
        self.assertEqual(http_exc.body, b'SPAM')
        self.assertEqual(exc_to_http_exc_mock.mock_calls, [
            call(sen.exc),
        ])


class Test_exc_to_http_exc(unittest.TestCase):

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_HTTPException_no_server_error(self, LOGGER):
        exc = HTTPNotFound()
        http_exc = exc_to_http_exc(exc)
        self.assertIs(http_exc, exc)
        self.assertEqual(http_exc.code, 404)
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY, 404),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_HTTPException_server_error(self, LOGGER):
        exc = HTTPInternalServerError()
        http_exc = exc_to_http_exc(exc)
        self.assertIs(http_exc, exc)
        self.assertEqual(http_exc.code, 500)
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, exc, ANY, 500, exc_info=True),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_subclass_of_DataLookupError(self, LOGGER):
        class MyCustomError(DataLookupError): pass
        exc = MyCustomError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPNotFound)
        self.assertEqual(http_exc.code, 404)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_subclass_of_DataLookupError_2(self, LOGGER):
        class MyCustomError(DataLookupError): pass
        exc = MyCustomError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPNotFound)
        self.assertEqual(http_exc.code, 404)
        self.assertEqual(http_exc.detail,  # detail == `DataLookupError.default public message`
                         DataLookupError.default_public_message)
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_subclass_of_DataLookupError_3(self, LOGGER):
        class MyCustomError(DataLookupError):
            default_public_message = 'own_default'
        exc = MyCustomError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPNotFound)
        self.assertEqual(http_exc.code, 404)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_subclass_of_DataLookupError_4(self, LOGGER):
        class MyCustomError(DataLookupError):
            default_public_message = 'own_default'
        exc = MyCustomError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPNotFound)
        self.assertEqual(http_exc.code, 404)
        self.assertEqual(http_exc.detail,  # detail == `MyCustomError.default public message`
                         'own_default')
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_AuthorizationError(self, LOGGER):
        exc = AuthorizationError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPForbidden)
        self.assertEqual(http_exc.code, 403)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_AuthorizationError_2(self, LOGGER):
        exc = AuthorizationError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPForbidden)
        self.assertEqual(http_exc.code, 403)
        self.assertEqual(http_exc.detail,  # detail == default public message
                         AuthorizationError.default_public_message)
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_DataFromClientError(self, LOGGER):
        exc = DataFromClientError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPBadRequest)
        self.assertEqual(http_exc.code, 400)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_DataFromClientError_2(self, LOGGER):
        exc = DataFromClientError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPBadRequest)
        self.assertEqual(http_exc.code, 400)
        self.assertEqual(http_exc.detail,  # detail == default public message
                         DataFromClientError.default_public_message)
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_ParamCleaningError(self, LOGGER):
        exc = ParamCleaningError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPBadRequest)
        self.assertEqual(http_exc.code, 400)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_ParamCleaningError_2(self, LOGGER):
        exc = ParamCleaningError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPBadRequest)
        self.assertEqual(http_exc.code, 400)
        self.assertEqual(http_exc.detail,  # detail == default public message
                         ParamCleaningError.default_public_message)
        self.assertEqual(LOGGER.mock_calls, [
            call.debug(ANY, exc, ANY),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_ResultCleaningError(self, LOGGER):
        exc = ResultCleaningError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPInternalServerError)
        self.assertEqual(http_exc.code, 500)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, exc, ANY, exc_info=True),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_ResultCleaningError_2(self, LOGGER):
        exc = ResultCleaningError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPInternalServerError)
        self.assertEqual(http_exc.code, 500)
        self.assertIs(http_exc.detail, None)  # *no* detail
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, exc, ANY, exc_info=True),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_other_DataAPIError(self, LOGGER):
        exc = DataAPIError(public_message='FOO')  # custom public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPInternalServerError)
        self.assertEqual(http_exc.code, 500)
        self.assertEqual(http_exc.detail, 'FOO')  # detail == custom public message
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, exc, ANY, exc_info=True),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_other_DataAPIError_2(self, LOGGER):
        exc = DataAPIError()  # no specific public message
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPInternalServerError)
        self.assertEqual(http_exc.code, 500)
        self.assertIs(http_exc.detail, None)  # *no* detail
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, exc, ANY, exc_info=True),
        ])

    @patch('n6sdk.pyramid_commons._pyramid_commons.LOGGER')
    def test_other_exception(self, LOGGER):
        exc = ZeroDivisionError
        http_exc = exc_to_http_exc(exc)
        self.assertIsInstance(http_exc, HTTPInternalServerError)
        self.assertEqual(http_exc.code, 500)
        self.assertIs(http_exc.detail, None)  # no detail
        self.assertEqual(LOGGER.mock_calls, [
            call.error(ANY, exc, exc_info=True),
        ])

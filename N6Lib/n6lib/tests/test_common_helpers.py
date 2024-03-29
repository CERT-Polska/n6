# Copyright (c) 2013-2021 NASK. All rights reserved.

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import (
    MagicMock,
    call,
    mock_open,
    patch,
    sentinel,
)

from unittest_expander import (
    foreach,
    expand,
    param,
)

from n6lib.common_helpers import (
    EMAIL_OVERRESTRICTED_SIMPLE_REGEX,
    AtomicallySavedFile,
    PlainNamespace,
    RsyncFileContextManager,
    dump_condensed_debug_msg,
    exiting_on_exception,
    make_condensed_debug_msg,
    replace_segment,
    read_file,
)



class Test__EMAIL_OVERRESTRICTED_SIMPLE_REGEX(unittest.TestCase):

    valid = [
        'foo@example.com',
        'foo.bar@example.com',
        'Foo.Bar@example.com',
        '-@example.com',
        '_@example.com',
        '!#$%&\'*+-/=?^_`{|}@example.com',  # see: http://en.wikipedia.org/wiki/Email_address#Local_part
        'foo@hyphen-ed.exa--mple.com',
    ]

    not_valid = [
        'foo.example.com',
        'foo@bar@example.com',
        '(foo)@example.com',
        '.foo@example.com',
        'foo.@example.com',
        'foo..bar@example.com',
        'foo@example-.com',
        'foo@-example.com',
        'foo@example.-com',
        'foo@example.com-',
        'foo@exam_ple.com',
        'foo@example.{}.com'.format('x' * 64),
        'foo@EXAMPLE.com',
    ]

    def test_valid(self):
        for v in self.valid:
            self.assertIsNotNone(EMAIL_OVERRESTRICTED_SIMPLE_REGEX.search(v))

    def test_not_valid(self):
        for v in self.not_valid:
            self.assertIsNone(EMAIL_OVERRESTRICTED_SIMPLE_REGEX.search(v))



### TODO: Test__... other constants (at least those not tested in SDK)



@patch('n6lib.common_helpers.subprocess.check_output')
@patch('n6lib.common_helpers.shutil.rmtree')
@patch('n6lib.common_helpers.tempfile.mkdtemp')
@patch('n6lib.common_helpers.open', new_callable=mock_open, read_data='written_data', create=True)
class TestRsyncFileContextManager(unittest.TestCase):

    def setUp(self):
        self.option = '-az'
        self.source = 'test_rsync_server'
        self.dest_tmp_file_name = "test_dest_file"
        self.temp_dir = 'tmp/tempdir'
        self.full_file_path = os.path.join(self.temp_dir, self.dest_tmp_file_name)
        self.manager = RsyncFileContextManager(self.option, self.source, self.dest_tmp_file_name)

    def test_normal_use(self, mock_opener, mock_temp_mkd, mock_shut_rmt, mock_subp_chout):
        mock_temp_mkd.return_value = self.temp_dir

        with self.manager as the_file:
            self.assertEqual(mock_temp_mkd.mock_calls, [call()])
            self.assertEqual(
                mock_subp_chout.mock_calls,
                [call(['rsync', self.option, self.source, self.full_file_path],
                      stderr=subprocess.STDOUT)])
            self.assertEqual(mock_opener.mock_calls, [call(self.full_file_path)])
            self.assertEqual(the_file.read(), 'written_data')
            self.assertEqual(the_file.close.mock_calls, [])
            self.assertEqual(mock_shut_rmt.mock_calls, [])
        self.assertEqual(the_file.close.mock_calls, [call()])
        self.assertEqual(mock_shut_rmt.mock_calls, [call(self.temp_dir)])
        self.assertIs(mock_opener(), the_file)

    def test_call_with_exception_in_enter(self, mock_opener, mock_temp_mkd,
                                          mock_shut_rmt, mock_subp_chout):
        mock_temp_mkd.return_value = self.temp_dir
        mock_subp_chout.side_effect = subprocess.CalledProcessError(
            returncode=42,
            cmd=sentinel.cmd,
            output=sentinel.output
        )

        with self.assertRaisesRegex(RuntimeError,
                                     r'^Cannot download source file.*\bsentinel'
                                     r'\.cmd\b.*42.*\bsentinel\.output\b'):
            with self.manager:
                pass
        self.assertEqual(mock_temp_mkd.mock_calls, [call()])
        self.assertEqual(
            mock_subp_chout.mock_calls,
            [call(['rsync', self.option, self.source, self.full_file_path],
                  stderr=subprocess.STDOUT)])
        self.assertEqual(mock_opener.mock_calls, [])
        self.assertEqual(mock_shut_rmt.mock_calls, [call(self.temp_dir)])

    def test_with_exception(self, mock_opener, mock_temp_mkd, mock_shut_rmt, mock_subp_chout):
        mock_temp_mkd.return_value = self.temp_dir

        with self.assertRaisesRegex(Exception, r'\Afoo bar\Z'):
            with self.manager as the_file:
                self.assertEqual(mock_temp_mkd.mock_calls, [call()])
                self.assertEqual(
                    mock_subp_chout.mock_calls,
                    [call(['rsync', self.option, self.source, self.full_file_path],
                          stderr=subprocess.STDOUT)])
                self.assertEqual(mock_opener.mock_calls, [call(self.full_file_path)])
                self.assertEqual(the_file.close.mock_calls, [])
                self.assertEqual(mock_shut_rmt.mock_calls, [])
                raise Exception('foo bar')
        self.assertEqual(the_file.close.mock_calls, [call()])
        self.assertEqual(mock_shut_rmt.mock_calls, [call(self.temp_dir)])
        self.assertIs(mock_opener(), the_file)

    def test_reuse_manager_instance(
            self, mock_opener, mock_temp_mkd, mock_shut_rmt, mock_subp_chout):
        mock_temp_mkd.return_value = self.temp_dir

        with self.manager as the_file1:
            self.assertEqual(mock_temp_mkd.mock_calls, [call()])
            self.assertEqual(
                mock_subp_chout.mock_calls,
                [call(['rsync', self.option, self.source, self.full_file_path],
                      stderr=subprocess.STDOUT)])
            self.assertEqual(mock_opener.mock_calls, [call(self.full_file_path)])
            self.assertEqual(the_file1.read(), 'written_data')
            self.assertEqual(the_file1.close.mock_calls, [])
            self.assertEqual(mock_shut_rmt.mock_calls, [])
        self.assertEqual(the_file1.close.mock_calls, [call()])
        self.assertEqual(mock_shut_rmt.mock_calls, [call(self.temp_dir)])
        self.assertIs(mock_opener(), the_file1)

        mock_temp_mkd.reset_mock()
        mock_subp_chout.reset_mock()
        mock_shut_rmt.reset_mock()

        # Unfortunately, we cannot reset the `mock_opener` mock
        # (because the `mock` library raises a `maximum recursion
        # depth exceeded` error -- bug in the library?).  That's
        # why `the_file2` (used below) "inherits" all calls of
        # `the_file1` (used above).

        with self.manager as the_file2:
            self.assertEqual(mock_temp_mkd.mock_calls, [call()])
            self.assertEqual(mock_subp_chout.mock_calls, [
                call(['rsync', self.option, self.source, self.full_file_path],
                     stderr=subprocess.STDOUT)])
            self.assertEqual(mock_opener.call_args, call(self.full_file_path))
            self.assertEqual(the_file2.read(), 'written_data')
            self.assertEqual(the_file2.close.mock_calls, [call()])
            self.assertEqual(mock_shut_rmt.mock_calls, [])
        self.assertEqual(the_file2.close.mock_calls, [call(), call()])
        self.assertEqual(mock_shut_rmt.mock_calls, [call(self.temp_dir)])
        self.assertIs(mock_opener(), the_file2)

    def test_nested_reuse_manager_instance(
            self, mock_opener, mock_temp_mkd, mock_shut_rmt, mock_subp_chout):
        with self.manager:
            with self.assertRaisesRegex(RuntimeError, r'^Context manager.*is not reentrant'):
                with self.manager:
                    pass



class TestPlainNamespace(unittest.TestCase):

    def setUp(self):
        self.obj = PlainNamespace(a=sentinel.a, bb=sentinel.bb)
        self.obj.self = sentinel.self

    def test_attributes(self):
        self.assertIs(self.obj.a, sentinel.a)
        self.assertIs(self.obj.bb, sentinel.bb)
        self.assertIs(self.obj.self, sentinel.self)
        self.assertFalse(hasattr(self.obj, 'xxxx'))
        del self.obj.bb
        self.assertFalse(hasattr(self.obj, 'bb'))

    def test_repr(self):
        self.obj.xxxx = 'xxxx'
        self.assertEqual(repr(self.obj),
                         "PlainNamespace(a=sentinel.a, bb=sentinel.bb, "
                         "self=sentinel.self, xxxx='xxxx')")
        self.assertEqual(repr(PlainNamespace()), "PlainNamespace()")

    def test_eq(self):
        obj2 = PlainNamespace(a=sentinel.a, bb=sentinel.bb, self=sentinel.self)
        obj3 = PlainNamespace(a=sentinel.a, bb=sentinel.bb)
        obj_empty = PlainNamespace()
        self.assertTrue(self.obj == self.obj)
        self.assertTrue(obj2 == obj2)
        self.assertTrue(obj3 == obj3)
        self.assertTrue(obj_empty == obj_empty)
        self.assertTrue(self.obj == obj2)
        self.assertTrue(obj2 == self.obj)
        self.assertFalse(self.obj == obj3)
        self.assertFalse(obj3 == self.obj)
        self.assertFalse(self.obj == obj_empty)
        self.assertFalse(obj_empty == self.obj)
        self.assertFalse(obj2 == obj3)
        self.assertFalse(obj3 == obj2)
        self.assertFalse(obj2 == obj_empty)
        self.assertFalse(obj_empty == obj2)
        self.assertFalse(obj3 == obj_empty)
        self.assertFalse(obj_empty == obj3)
        del obj2.self
        self.assertTrue(obj2 == obj2)
        self.assertTrue(obj2 == obj3)
        self.assertTrue(obj3 == obj2)
        self.assertFalse(self.obj == obj2)
        self.assertFalse(obj2 == self.obj)
        self.assertFalse(obj2 == obj_empty)
        self.assertFalse(obj_empty == obj2)
        del obj2.a, obj2.bb
        self.assertTrue(obj2 == obj2)
        self.assertTrue(obj2 == obj_empty)
        self.assertTrue(obj_empty == obj2)
        self.assertFalse(self.obj == obj2)
        self.assertFalse(obj2 == self.obj)
        self.assertFalse(obj2 == obj3)
        self.assertFalse(obj3 == obj2)

    def test_ne(self):
        obj2 = PlainNamespace(a=sentinel.a, bb=sentinel.bb, self=sentinel.self)
        obj3 = PlainNamespace(a=sentinel.a, bb=sentinel.bb)
        obj_empty = PlainNamespace()
        self.assertFalse(self.obj != self.obj)
        self.assertFalse(obj2 != obj2)
        self.assertFalse(obj3 != obj3)
        self.assertFalse(obj_empty != obj_empty)
        self.assertFalse(self.obj != obj2)
        self.assertFalse(obj2 != self.obj)
        self.assertTrue(self.obj != obj3)
        self.assertTrue(obj3 != self.obj)
        self.assertTrue(self.obj != obj_empty)
        self.assertTrue(obj_empty != self.obj)
        self.assertTrue(obj2 != obj3)
        self.assertTrue(obj3 != obj2)
        self.assertTrue(obj2 != obj_empty)
        self.assertTrue(obj_empty != obj2)
        self.assertTrue(obj3 != obj_empty)
        self.assertTrue(obj_empty != obj3)
        del obj2.self
        self.assertFalse(obj2 != obj2)
        self.assertFalse(obj2 != obj3)
        self.assertFalse(obj3 != obj2)
        self.assertTrue(self.obj != obj2)
        self.assertTrue(obj2 != self.obj)
        self.assertTrue(obj2 != obj_empty)
        self.assertTrue(obj_empty != obj2)
        del obj2.a, obj2.bb
        self.assertFalse(obj2 != obj2)
        self.assertFalse(obj2 != obj_empty)
        self.assertFalse(obj_empty != obj2)
        self.assertTrue(self.obj != obj2)
        self.assertTrue(obj2 != self.obj)
        self.assertTrue(obj2 != obj3)
        self.assertTrue(obj3 != obj2)

    def test_error_on_positional_constructor_args(self):
        with self.assertRaises(TypeError):
            PlainNamespace('a')
        with self.assertRaises(TypeError):
            PlainNamespace('a', 'bb')
        with self.assertRaises(TypeError):
            PlainNamespace('xyz', a=sentinel.a, bb=sentinel.bb)



@expand
class Test__exiting_on_exception(unittest.TestCase):

    @foreach(
        param(
            decorator_kwargs=None,
            expected_exc_class=SystemExit,
            expected_regex_pattern_prefix=r'^FATAL ERROR!.*',
        ),
        param(
            decorator_kwargs=dict(),
            expected_exc_class=SystemExit,
            expected_regex_pattern_prefix=r'^FATAL ERROR!.*',
        ),
        param(
            decorator_kwargs=dict(
                exc_message_pattern='custom text, {traceback_msg}'
            ),
            expected_exc_class=SystemExit,
            expected_regex_pattern_prefix=r'^custom text.*',
        ),
        param(
            decorator_kwargs=dict(
                exc_factory=RuntimeError,
            ),
            expected_exc_class=RuntimeError,
            expected_regex_pattern_prefix=r'^FATAL ERROR!.*',
        ),
        param(
            decorator_kwargs=dict(
                exc_factory=RuntimeError,
                exc_message_pattern='custom text, {traceback_msg}',
            ),
            expected_exc_class=RuntimeError,
            expected_regex_pattern_prefix=r'^custom text.*',
        ),
    )
    @foreach(
        param(
            raised_exc=ValueError,
            expected_regex_pattern_suffix=r'\bValueError\b',
        ),
        param(
            raised_exc=ValueError('foobar'),
            expected_regex_pattern_suffix=r'\bValueError\b.*\bfoobar\b',
        ),
        param(
            raised_exc=Exception,
            expected_regex_pattern_suffix=r'\bException\b',
        ),
        param(
            raised_exc=Exception('foobar'),
            expected_regex_pattern_suffix=r'\bException\b.*\bfoobar\b',
        ),
        param(
            raised_exc=BaseException,
            expected_regex_pattern_suffix=r'\bBaseException\b',
        ),
        param(
            raised_exc=BaseException('foobar'),
            expected_regex_pattern_suffix=r'\bBaseException\b.*\bfoobar\b',
        ),
    )
    def test_with_various_exceptions(self,
                                     decorator_kwargs,
                                     raised_exc,
                                     expected_exc_class,
                                     expected_regex_pattern_prefix,
                                     expected_regex_pattern_suffix):
        m = MagicMock()
        expected_regex_pattern = expected_regex_pattern_prefix + expected_regex_pattern_suffix
        expected_regex = re.compile(expected_regex_pattern, re.DOTALL)

        if decorator_kwargs is None:
            @exiting_on_exception
            def some_callable(*args, **kwargs):
                m(*args, **kwargs)
                raise raised_exc
        else:
            @exiting_on_exception(**decorator_kwargs)
            def some_callable(*args, **kwargs):
                m(*args, **kwargs)
                raise raised_exc

        with self.assertRaisesRegex(expected_exc_class, expected_regex) as cm:
            some_callable(42, b='spam')

        self.assertEqual(m.mock_calls, [call(42, b='spam')])
        assert ('FATAL ERROR' in str(cm.exception) or
                'custom text' in str(cm.exception)), 'bug in the test'


    @foreach(
        param(decorator_kwargs=None),
        param(decorator_kwargs=dict()),
        param(decorator_kwargs=dict(exc_message_pattern='custom text, {traceback_msg}')),
        param(decorator_kwargs=dict(exc_factory=RuntimeError)),
        param(decorator_kwargs=dict(
            exc_factory=RuntimeError,
            exc_message_pattern='custom text, {traceback_msg}',
        )),
    )
    @foreach(
        param(
            raised_exc=SystemExit,
            expected_exc_class=SystemExit,
            expected_exc_args=(),
            is_expected_the_same_exc=False,
        ),
        param(
            raised_exc=SystemExit(0),
            expected_exc_class=SystemExit,
            expected_exc_args=(0,),
            is_expected_the_same_exc=True,
        ),
        param(
            raised_exc=SystemExit(1),
            expected_exc_class=SystemExit,
            expected_exc_args=(1,),
            is_expected_the_same_exc=True,
        ),
        param(
            raised_exc=SystemExit('foobar'),
            expected_exc_class=SystemExit,
            expected_exc_args=('foobar',),
            is_expected_the_same_exc=True,
        ),
        param(
            raised_exc=KeyboardInterrupt,
            expected_exc_class=KeyboardInterrupt,
            expected_exc_args=(),
            is_expected_the_same_exc=False,
        ),
        param(
            raised_exc=KeyboardInterrupt('foobar', 'spamham'),
            expected_exc_class=KeyboardInterrupt,
            expected_exc_args=('foobar', 'spamham'),
            is_expected_the_same_exc=True,
        ),
    )
    def test_with_SystemExit_or_KeyboardInterrupt(self,
                                                  decorator_kwargs,
                                                  raised_exc,
                                                  expected_exc_class,
                                                  expected_exc_args,
                                                  is_expected_the_same_exc):
        m = MagicMock()

        if decorator_kwargs is None:
            @exiting_on_exception
            def some_callable(*args, **kwargs):
                m(*args, **kwargs)
                raise raised_exc
        else:
            @exiting_on_exception(**decorator_kwargs)
            def some_callable(*args, **kwargs):
                m(*args, **kwargs)
                raise raised_exc

        with self.assertRaises(expected_exc_class) as cm:
            some_callable(42, b='spam')

        self.assertEqual(m.mock_calls, [call(42, b='spam')])
        self.assertEqual(cm.exception.args, expected_exc_args)
        if is_expected_the_same_exc:
            self.assertIs(cm.exception, raised_exc)
        else:
            self.assertIsNot(cm.exception, raised_exc)
        self.assertNotIn('FATAL ERROR', str(cm.exception))
        self.assertNotIn('custom text', str(cm.exception))


    @foreach(
        param(decorator_kwargs=None),
        param(decorator_kwargs=dict()),
        param(decorator_kwargs=dict(exc_message_pattern='custom text, {traceback_msg}')),
        param(decorator_kwargs=dict(exc_factory=RuntimeError)),
        param(decorator_kwargs=dict(
            exc_factory=RuntimeError,
            exc_message_pattern='custom text, {traceback_msg}',
        )),
    )
    def test_without_any_exception(self, decorator_kwargs):
        m = MagicMock()

        if decorator_kwargs is None:
            @exiting_on_exception
            def some_callable(*args, **kwargs):
                m(*args, **kwargs)
                return sentinel.result
        else:
            @exiting_on_exception(**decorator_kwargs)
            def some_callable(*args, **kwargs):
                m(*args, **kwargs)
                return sentinel.result

        result = some_callable(42, b='spam')

        self.assertIs(result, sentinel.result)
        self.assertEqual(m.mock_calls, [call(42, b='spam')])



class Test__replace_segment(unittest.TestCase):

    def test_with_non_negative_indexes(self):
        self.assertEqual(replace_segment('foo.bar..spam', 0, 'REPLACED'),
                         'REPLACED.bar..spam')
        self.assertEqual(replace_segment('foo.bar..spam', 1, b'REPLACED'),
                         'foo.REPLACED..spam')
        self.assertEqual(replace_segment(b'foo.bar..spam', 2, 'REPLACED'),
                         b'foo.bar.REPLACED.spam')
        self.assertEqual(replace_segment(b'foo.bar..spam', 3, b'REPLACED'),
                         b'foo.bar..REPLACED')
        with self.assertRaises(IndexError):
            replace_segment('foo.bar..spam', 4, 'REPLACED')

    def test_with_negative_indexes(self):
        self.assertEqual(replace_segment('foo.bar..spam', -1, 'REPLACED'),
                         'foo.bar..REPLACED')
        self.assertEqual(replace_segment('foo.bar..spam', -2, b'REPLACED'),
                         'foo.bar.REPLACED.spam')
        self.assertEqual(replace_segment(b'foo.bar..spam', -3, 'REPLACED'),
                         b'foo.REPLACED..spam')
        self.assertEqual(replace_segment(b'foo.bar..spam', -4, b'REPLACED'),
                         b'REPLACED.bar..spam')
        with self.assertRaises(IndexError):
            replace_segment('foo.bar..spam', -5, 'REPLACED')

    def test_single_with_non_negative_indexes(self):
        self.assertEqual(replace_segment('foo', 0, 'REPLACED'), 'REPLACED')
        self.assertEqual(replace_segment(b'', 0, b'REPLACED'), b'REPLACED')
        with self.assertRaises(IndexError):
            replace_segment(b'foo', 1, b'REPLACED')
        with self.assertRaises(IndexError):
            replace_segment('', 1, 'REPLACED')

    def test_single_with_negative_indexes(self):
        self.assertEqual(replace_segment(b'foo', -1, 'REPLACED'), b'REPLACED')
        self.assertEqual(replace_segment('', -1, 'REPLACED'), 'REPLACED')
        with self.assertRaises(IndexError):
            replace_segment('foo', -2, 'REPLACED')
        with self.assertRaises(IndexError):
            replace_segment(b'', -2, 'REPLACED')

    def test_custom_separator_with_non_negative_indexes(self):
        self.assertEqual(replace_segment('foo.bar..spam', 0,
                                         'REPLACED', sep='..'),
                         'REPLACED..spam')
        self.assertEqual(replace_segment(b'foo.bar..spam', 1,
                                         b'REPLACED', sep=b'..'),
                         b'foo.bar..REPLACED')
        with self.assertRaises(IndexError):
            replace_segment('foo.bar..spam', 2, 'REPLACED', sep='..')

    def test_custom_separator_with_negative_indexes(self):
        self.assertEqual(replace_segment(b'foo.bar..spam', -1,
                                         b'REPLACED', sep='..'),
                         b'foo.bar..REPLACED')
        self.assertEqual(replace_segment('foo.bar..spam', -2,
                                         'REPLACED', sep='..'),
                         'REPLACED..spam')
        with self.assertRaises(IndexError):
            replace_segment(b'foo.bar..spam', -3, b'REPLACED', sep=b'..')



class Test__read_file(unittest.TestCase):

# TODO: divide into three separate tests:
#    def test_text_implicit_encoding_utf8(self):
#    def test_text_custom_encoding(self):
#    def test_binary(self):
    def test(self):
        expected_data = 'foo bar\nspam'
        open_mock = mock_open(read_data=expected_data)
        with patch('builtins.open', open_mock):
            actual_data = read_file('/some/file.txt', 'r+', some_kw_arg=1)
        self.assertEqual(actual_data, expected_data)
        self.assertEqual(open_mock.mock_calls, [
            call('/some/file.txt', 'r+', some_kw_arg=1, encoding='utf-8'),
            call().__enter__(),
            call().read(),
            call().__exit__(None, None, None),
        ])

        expected_data = 'foo bar\nspam'
        encoding = 'Foo Bar'
        open_mock = mock_open(read_data=expected_data)
        with patch('builtins.open', open_mock):
            actual_data = read_file('/some/file.txt', 'r+', some_kw_arg=1, encoding=encoding)
        self.assertEqual(actual_data, expected_data)
        self.assertEqual(open_mock.mock_calls, [
            call('/some/file.txt', 'r+', some_kw_arg=1, encoding=encoding),
            call().__enter__(),
            call().read(),
            call().__exit__(None, None, None),
        ])

        expected_data = b'foo bar\nspam'
        open_mock = mock_open(read_data=expected_data)
        with patch('builtins.open', open_mock):
            actual_data = read_file('/some/file.txt', 'r+b', some_kw_arg=1)
        self.assertEqual(actual_data, expected_data)
        self.assertEqual(open_mock.mock_calls, [
            call('/some/file.txt', 'r+b', some_kw_arg=1),  # Note: no `encoding='utf-8'`
            call().__enter__(),
            call().read(),
            call().__exit__(None, None, None),
        ])


class TestMakeDebugMsg(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # prepare a sample traceback object
        try:
            raise ValueError('ValueError msg')
        except ValueError:
            cls.sample_traceback = sys.exc_info()[-1]

    @classmethod
    def tearDownClass(cls):
        # noinspection PyUnresolvedReferences
        del cls.sample_traceback  # avoiding keeping reference cycles

    def test_make_condensed_debug_msg_exc_info(self):
        """ Test handling exc_info param. """

        # Full debug message
        full_debug_msg = re.compile(r"^\[.+@.+\] ValueError:.+ValueError msg.+raise ValueError"
                                    r"\('ValueError msg'\).+test_common_helpers.+[`\]]$")
        test_full_debug_msg = make_condensed_debug_msg((ValueError,
                                                        'ValueError msg',
                                                        self.sample_traceback))
        # self.assertTrue(full_debug_msg.findall(test_full_debug_msg))
        self.assertRegex(text=test_full_debug_msg,
                         expected_regex=full_debug_msg)

        # No traceback provided
        no_traceback_msg = re.compile(r"^\[.+@.+\] ValueError:.+ValueError msg.+"
                                      r"\<no traceback\>.+test_common_helpers.+[`\]]$")
        test_no_traceback_msg = make_condensed_debug_msg((ValueError,
                                                          'ValueError msg',
                                                          None))
        self.assertRegex(text=test_no_traceback_msg,
                         expected_regex=no_traceback_msg)

        # 3x none in the tuple
        nones_tuple_msg = re.compile(r"^\[.+@.+\] \<no exc\>:.+\<no msg\>.+"
                                     r"\<no traceback\>.+test_common_helpers.+[`\]]$")
        test_nones_tuple_msg = make_condensed_debug_msg((None,
                                                         None,
                                                         None))
        self.assertRegex(text=test_nones_tuple_msg,
                         expected_regex=nones_tuple_msg)

        # exc_info param not provided, executed without exception handling
        normal_msg = re.compile(r"^\[.+@.+\] \<no exc\>:.+\<no msg\>.+"
                                r"\<no traceback\>.+test_common_helpers.+[`\]]$")
        assert sys.exc_info() == (None, None, None)
        test_normal_msg = make_condensed_debug_msg()
        self.assertRegex(text=test_normal_msg,
                         expected_regex=normal_msg)

        # exc_info param not provided, executed in a except block
        try:
            raise ValueError('ValueError msg')
        except ValueError:
            except_debug_msg = re.compile(r"^\[.+@.+\] ValueError:.+ValueError msg.+raise "
                                          r"ValueError\('ValueError msg'\).+"
                                          r"test_common_helpers.+[`\]]$")
            test_except_debug_msg = make_condensed_debug_msg()
            self.assertTrue(except_debug_msg.findall(test_except_debug_msg))


    def test_make_condensed_debug_msg(self):
        """Test if parts of debug msg are cut to proper lengths."""

        # char_limit for testing purposes
        test_limit = 20

        try:
            try:
                raise ValueError('very long exception message'
                                 'for test purposes')
            except ValueError:
                exc_info = sys.exc_info()

            exc_no_tb = (exc_info[0],
                         exc_info[1],
                         None)

            exc_no_msg = (exc_info[0],
                          None,
                          exc_info[2])

            # Test total_limit param
            self.assertLessEqual(len(make_condensed_debug_msg(exc_info, total_limit=test_limit)),
                                 test_limit)

            # Test exc_str with no message
            temp_debug_msg = make_condensed_debug_msg(exc_no_msg)

            exc_str_regexp = re.compile(r': \<no msg\> \<\<\= ')
            self.assertRegex(text=temp_debug_msg,
                             expected_regex=exc_str_regexp)

            # Test exc_str with message
            temp_debug_msg = make_condensed_debug_msg(exc_info,
                                                      exc_str_limit=test_limit)

            expected_msg_regex = re.compile(r': .+ \<\<\= ')
            extracted_msg = expected_msg_regex.findall(temp_debug_msg)[0][2:-5]
            self.assertLessEqual(len(extracted_msg),
                                 test_limit)

            # Test tb_str_limit with no traceback
            temp_debug_msg = make_condensed_debug_msg(exc_no_tb,
                                                      tb_str_limit=test_limit)
            tb_regexp = re.compile(r'\<\<\= \<no traceback\> \<\-\(\*\)\-')
            self.assertRegex(text=temp_debug_msg,
                             expected_regex=tb_regexp)

            # Test tb_str with traceback
            temp_debug_msg = make_condensed_debug_msg(exc_info,
                                                      tb_str_limit=test_limit)
            tb_regexp = re.compile(r'\<\<\= .+ \<\-\(\*\)\-')
            extracted_tb = tb_regexp.findall(temp_debug_msg)[0][4:-7]
            self.assertLessEqual(len(extracted_tb),
                                 test_limit)

            # Check stack_str_limit param
            temp_debug_msg = make_condensed_debug_msg(exc_info,
                                                      stack_str_limit=test_limit)
            stack_str = temp_debug_msg[temp_debug_msg.rfind('<-(*)- ')+7:]
            self.assertLessEqual(len(stack_str), test_limit)

            # Check alternative cut_indicator
            alt_cut_ind = '[-]'
            self.assertTrue(alt_cut_ind in make_condensed_debug_msg(total_limit=100,
                                                                    cut_indicator=alt_cut_ind))
        finally:
            exc_info = exc_no_msg = None  # avoiding keeping reference cycles


    def test_make_condensed_debug_msg_exceptions(self):
        """
        Test cases where ValueError should be raised
        when one of the char limits is smaller
        than cut indicator.
        """
        try:
            try:
                raise ValueError('ValueError happened!')
            except ValueError:
                test_exc_info = sys.exc_info()

            self.assertRaises(ValueError,
                              make_condensed_debug_msg,
                              test_exc_info,
                              total_limit=2,
                              cut_indicator='[...]')
            self.assertRaises(ValueError,
                              make_condensed_debug_msg,
                              test_exc_info,
                              exc_str_limit=2,
                              cut_indicator='[...]')
            self.assertRaises(ValueError,
                              make_condensed_debug_msg,
                              test_exc_info,
                              tb_str_limit=2,
                              cut_indicator='[...]')
            self.assertRaises(ValueError,
                              make_condensed_debug_msg,
                              test_exc_info,
                              stack_str_limit=2,
                              cut_indicator='[...]')
        finally:
            test_exc_info = None  # avoiding keeping reference cycles



@patch('sys.stderr')
@patch('sys.stdout')
class TestDumpDebugMsg(unittest.TestCase):

    # TODO: refactor (and maybe improve?) this method
    def test_dump_condensed_debug_msg(self, mock_stdout, mock_stderr):
        """
        Tests for dumping error msg to stdout and stderr.

        Args/kwargs:
            `mock_stdout`
                Mocked stdout from a decorator.
            `mock_stderr`
                Mocked stderr from a decorator.
        """
        assert sys.exc_info() == (None, None, None)

        # Dump debug msg to stdout
        stdout_msg = '<dump_condensed_debug_msg header stdout>'
        dump_condensed_debug_msg(stdout_msg, sys.stdout)
        stdout_call = list(mock_stdout.mock_calls)[0]
        self.assertTrue(stdout_msg in str(stdout_call))
        self.assertEqual(mock_stdout.mock_calls[-1], call.flush())

        # Dump debug msg to stderr
        stderr_msg = '<dump_condensed_debug_msg header stderr>'
        dump_condensed_debug_msg(stderr_msg, sys.stderr)
        stderr_call = list(mock_stderr.mock_calls)[0]
        self.assertTrue(stderr_msg in str(stderr_call))
        self.assertEqual(mock_stderr.mock_calls[-1], call.flush())

        mock_stderr.reset_mock()
        mock_stdout.reset_mock()

        # Test while handling exception
        try:
            raise ValueError('ValueError msg')
        except ValueError:
            # Dump exception debug msg to stdout
            exc_stdout_msg = re.compile(r"\\nstdout\\n\\nCONDENSED DEBUG INFO: \[.+\] \[.+@.+\] "
                                        r"ValueError:.+ValueError msg.+raise ValueError"
                                        r"\(\\?'ValueError msg\\?'\).+test_common_helpers.+`")
            dump_condensed_debug_msg(header='stdout', stream=sys.stdout)
            stdout_call = str(list(mock_stdout.mock_calls)[0])
            self.assertRegex(text=stdout_call,
                             expected_regex=exc_stdout_msg)
            self.assertEqual(mock_stdout.mock_calls[-1], call.flush())

            # Dump exception debug msg to stderr
            exc_stderr_msg = re.compile(r"\\nstderr\\n\\nCONDENSED DEBUG INFO: \[.+\] \[.+@.+\] "
                                        r"ValueError:.+ValueError msg.+raise ValueError"
                                        r"\(\\?'ValueError msg\\?'\).+test_common_helpers.+`")
            dump_condensed_debug_msg(header='stderr', stream=sys.stderr)
            stderr_call = str(list(mock_stderr.mock_calls)[0])
            self.assertRegex(text=stderr_call,
                             expected_regex=exc_stderr_msg)
            self.assertEqual(mock_stderr.mock_calls[-1], call.flush())

            # Same but specifying argument `debug_msg`
            mock_stderr.reset_mock()
            exc_stderr_msg = re.compile(r"\\nstderr\\n\\nCONDENSED DEBUG INFO: \[[^@]+\] "
                                        r"my_debug_msg\\n\W*\Z")
            dump_condensed_debug_msg(header='stderr', stream=sys.stderr, debug_msg='my_debug_msg')
            stderr_call = str(list(mock_stderr.mock_calls)[0])
            self.assertRegex(text=stderr_call,
                             expected_regex=exc_stderr_msg)
            self.assertEqual(mock_stderr.mock_calls[-1], call.flush())



class TestAtomicallySavedFile(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_file_path = os.path.join(self.tmp_dir, 'test_file.txt')

        with open(self.tmp_file_path, 'w') as file:
            file.write('original content')

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    # TODO: Add cases with custom encoding and with binary mode.
    def test_success(self):
        with AtomicallySavedFile(self.tmp_file_path, 'w') as file:
            file.write('changed content')

        actual_content = read_file(self.tmp_file_path)
        expected_content = 'changed content'
        self.assertEqual(expected_content, actual_content)

    def test_exception_before_writing_to_the_file(self):
        invalid_path = 'foo/bar/baz.txt'
        try:
            with AtomicallySavedFile(invalid_path, 'w') as file:
                pass
        except OSError:
            pass

        actual_content = read_file(self.tmp_file_path)
        expected_content = 'original content'
        self.assertEqual(expected_content, actual_content)

    def test_exception_while_writing_to_the_file(self):
        try:
            with AtomicallySavedFile(self.tmp_file_path, 'w') as file:
                file.write('changed content')
                raise Exception('Exception occurred while writing to the file')
        except Exception:
            pass

        actual_content = read_file(self.tmp_file_path)
        expected_content = 'original content'
        self.assertEqual(expected_content, actual_content)



# maybe TODO later: tests of the other classes and functions in
# n6lib.common_helpers.  Note that most of them are already tested
# with doctests (at least superficially)...

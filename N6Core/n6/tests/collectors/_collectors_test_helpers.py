# Copyright (c) 2013-2019 NASK. All rights reserved.

import collections
import datetime
import errno
import functools
import itertools
import os.path as osp
import Queue
import re
import unittest
import weakref
from argparse import ArgumentParser
from cStringIO import StringIO

import mock

from n6lib.common_helpers import (
    SimpleNamespace,
    reduce_indent,
)
from n6lib.config import (
    Config,
    ConfigSection,
)
from n6lib.datetime_helpers import datetime_utc_normalize
from n6lib.unit_test_helpers import TestCaseMixin



class _BaseCollectorTestCase(TestCaseMixin, unittest.TestCase):

    # These flags make it possible to turn on/off patching
    # of particular groups of stuff...
    patch_cmdline_args = True
    patch_config = True
    patch_QueuedBase = True
    patch_CollectorWithStateMixin = True
    patch_to_disable_legacy_collector_state_mixins = True


    def __init__(self, *args, **kwargs):
        super(_BaseCollectorTestCase, self).__init__(*args, **kwargs)

        self._ArgumentParser_parse_known_args = ArgumentParser.parse_known_args.__func__

        # The following mock is used by `prepare_collector()` to patch
        # the `n6.base.queue.QueuedBase.publish_output()` method.
        # In subclasses this mock can be, e.g.:
        # * used in assertions (obviously!),
        # * reconfigured (e.g., by setting `side_effect` on it...),
        #   or even entirely replaced with something else.
        self.publish_output_mock = mock.MagicMock()

        # The following attribute will automatically be set to the state being
        # saved by a stub of the `CollectorWithStateMixin.save_state()` method
        # (if it is patched, using the stub, by `prepare_collector()`).
        # In subclasses this attribute can be inspected to check
        # whether and what object has been passed in to `save_state()`.
        self.saved_state = mock.sentinel.NO_STATE


    # The following method is intended to be called in subclasses
    # (in their `test_*()` or `setUp()` methods).
    # Its functionality may be extended or modified in subclasses by:
    # * extending (using super()...) this method directly,
    # * extending (using super()...) the `do_patching()` method defined
    #   below,
    # * overriding the `make_*()` methods defined below.
    def prepare_collector(self,
                          collector_class,
                          config_content=None,
                          cmdline_args=(),
                          initial_state=mock.sentinel.NO_STATE):

        self.do_patching(config_content, cmdline_args, initial_state)

        init_kwargs = collector_class.get_script_init_kwargs()
        collector = collector_class(**init_kwargs)

        return collector


    def do_patching(self,
                    config_content=None,
                    cmdline_args=(),
                    initial_state=mock.sentinel.NO_STATE):

        self.patch('n6lib.config.Config._load_n6_config_files',
                   self._get_unmemoized_classmethod__Config__load_n6_config_files())

        for patch_target in self.iter_targets_to_be_patched_as_unsupported():
            self.patch_with_plug(patch_target)

        if self.patch_cmdline_args:
            fake_of__ArgumentParser_parse_known_args = \
                self.make_fake_of__ArgumentParser_parse_known_args(cmdline_args)
            self.patch_with_plug('argparse.open',
                                 exc_factory=functools.partial(IOError, errno.EPERM),
                                 create=True)
            self.patch('argparse.ArgumentParser.parse_known_args',
                       fake_of__ArgumentParser_parse_known_args)

        if self.patch_config:
            fake_of__RawConfigParser_read = self.make_fake_of__RawConfigParser_read(config_content)
            stub_of__Config__get_config_file_paths = self.make_stub_of__Config__get_config_file_paths()
            self.patch('ConfigParser.RawConfigParser.read',
                       fake_of__RawConfigParser_read)
            self.patch('n6lib.config.Config._get_config_file_paths',
                       stub_of__Config__get_config_file_paths)

        if self.patch_QueuedBase:
            (stub_of__QueuedBase___init__,
             stub_of__QueuedBase_run,
             stub_of__QueuedBase_stop,
             stub_of__QueuedBase_inner_stop) = self.make_stubs_of__QueuedBase_basic_methods()
            self.patch('n6.base.queue.QueuedBase.__init__',
                       stub_of__QueuedBase___init__)
            self.patch('n6.base.queue.QueuedBase.run',
                       stub_of__QueuedBase_run)
            self.patch('n6.base.queue.QueuedBase.stop',
                       stub_of__QueuedBase_stop)
            self.patch('n6.base.queue.QueuedBase.inner_stop',
                       stub_of__QueuedBase_inner_stop)
            self.patch('n6.base.queue.QueuedBase.publish_output',
                       self.publish_output_mock)

        if self.patch_CollectorWithStateMixin:
            stub_of__CollectorWithStateMixin_load_state = \
                self.make_stub_of__CollectorWithStateMixin_load_state(initial_state)
            stub_of__CollectorWithStateMixin_save_state = \
                self.make_stub_of__CollectorWithStateMixin_save_state()
            self.patch('n6.collectors.generic.CollectorWithStateMixin.load_state',
                       stub_of__CollectorWithStateMixin_load_state)
            self.patch('n6.collectors.generic.CollectorWithStateMixin.save_state',
                       stub_of__CollectorWithStateMixin_save_state)


    def _get_unmemoized_classmethod__Config__load_n6_config_files(self):
        return classmethod(getattr(Config._load_n6_config_files.__func__,
                                   'func',
                                   Config._load_n6_config_files.__func__))


    def iter_targets_to_be_patched_as_unsupported(self):

        if self.patch_QueuedBase:
            # An explicit `NotImplementedError` will be raised if one of
            # these objects/methods is used by accident (it shouldn't as
            # anything that could cause that is faked/stubbed/mocked in
            # `do_patching()`...).
            yield 'n6.base.queue.pika'
            yield 'n6.base.queue.QueuedBase.connect'

        if self.patch_to_disable_legacy_collector_state_mixins:
            # An explicit `NotImplementedError` will be raised if a tested
            # collector causes that the `get_cache_file_name()` method of
            # one of these *deprecated* mixins is called (note that a newer
            # mixin class -- `CollectorWithStateMixin` -- should be used
            # instead of them).
            yield 'n6.collectors.generic.CollectorStateMixIn.get_cache_file_name'
            yield 'n6.collectors.generic.CollectorStateMixInPlus.get_cache_file_name'


    def make_fake_of__ArgumentParser_parse_known_args(self, cmdline_args=()):

        orig__ArgumentParser_parse_known_args = self._ArgumentParser_parse_known_args

        def fake_of__ArgumentParser_parse_known_args(self, args=None, namespace=None):
            if args is None:
                args = list(cmdline_args)
            return orig__ArgumentParser_parse_known_args(self, args, namespace)

        return fake_of__ArgumentParser_parse_known_args


    def make_fake_of__RawConfigParser_read(self, config_content=None):

        adjusted_config_content = reduce_indent(config_content or '')

        def fake_of__RawConfigParser_read(self, filenames):
            if isinstance(filenames, basestring):
                filenames = [filenames]
            fp = StringIO(adjusted_config_content)
            for name in filenames:
                # (only for the first of filenames `fp` will offer any content)
                self.readfp(fp, name)
            read_ok = list(filenames)
            return read_ok

        return fake_of__RawConfigParser_read


    def make_stub_of__Config__get_config_file_paths(self):

        example_filename = 'we-are-just-testing-with-{}'.format(self.__class__.__name__)

        # noinspection PyDecorator
        @staticmethod
        def stub_of__Config__get_config_file_paths(path):
            return [osp.join(path, example_filename)]

        return stub_of__Config__get_config_file_paths


    def make_stubs_of__QueuedBase_basic_methods(self):

        # actual stub definitions

        def stub_of__QueuedBase___init__(self, **_):
            self._conn_params_dict = {'heartbeat_interval': 30}
            self.clear_amqp_communication_state_attributes()

        def stub_of__QueuedBase_run(self):
            self._connection = SimpleNamespace(add_timeout=_add_timeout,
                                               outbound_buffer=collections.deque())
            self.output_ready = True
            try:
                try:
                    self.start_publishing()
                    for callback in _consume_timeout_callbacks():
                        callback()
                finally:
                    _clear_timeout_callbacks()
            finally:
                self._ensure_publishing_generator_closed()

        def stub_of__QueuedBase_stop(self):
            self.inner_stop()

        def stub_of__QueuedBase_inner_stop(self):
            self._closing = True
            self.output_ready = False

        # internal helpers

        _timeout_callbacks = Queue.PriorityQueue()
        _timeout_callbacks_priority_tie_breaker_gen = itertools.count()
        _pseudo_time = [0.0]

        def _add_timeout(delay, callback):
            deadline = _pseudo_time[0] + delay
            priority_tie_breaker = next(_timeout_callbacks_priority_tie_breaker_gen)
            _timeout_callbacks.put((deadline, priority_tie_breaker, callback))

        def _consume_timeout_callbacks():
            while True:
                try:
                    deadline, _, callback = _timeout_callbacks.get_nowait()
                except Queue.Empty:
                    break
                _pseudo_time[0] = deadline
                yield callback

        def _clear_timeout_callbacks():
            list(_consume_timeout_callbacks())

        return (stub_of__QueuedBase___init__,
                stub_of__QueuedBase_run,
                stub_of__QueuedBase_stop,
                stub_of__QueuedBase_inner_stop)


    def make_stub_of__CollectorWithStateMixin_load_state(self,
                                                         initial_state=mock.sentinel.NO_STATE):
        if initial_state is mock.sentinel.NO_STATE:
            def stub_of__CollectorWithStateMixin_load_state(self):
                return self.make_default_state()
        else:
            def stub_of__CollectorWithStateMixin_load_state(self):
                return initial_state

        return stub_of__CollectorWithStateMixin_load_state


    def make_stub_of__CollectorWithStateMixin_save_state(self):

        test_case = weakref.proxy(self)

        def stub_of__CollectorWithStateMixin_save_state(self, state):
            test_case.saved_state = state

        return stub_of__CollectorWithStateMixin_save_state



class _TestMailCollectorsBaseClass(TestCaseMixin, unittest.TestCase):

    """
    A base class for testing e-mail sources' collectors.

    To test a collector, you need to create a subclass that provides
    one of the following sets of attributes:

    * variant I (recommended as it enables less auto-magic, and
      possibly more exhaustive, way of testing than variant II):

      * `collector_class`
      * `expected_source_channel`
      * `expected_output_data_body`
      * `additional_config_opts` (optional)
      * `raw_email`
      * `expected_mail_time`

    * variant II (legacy, more auto-magic):

      * `collector_class`
      * `expected_source_channel`
      * `expected_output_data_body`
      * `additional_config_opts` (optional)
      * `message_content`
      * `email_subject`
      * `email_items` (may be overridden but the default content should
         be OK in most cases)
      * `additional_headers` (optional)

    The `collector_class` attribute should be set to the tested
    collector class.

    The `expected_source_channel` should be set to a string equal to
    the expected "channel" part (the second segment) of the source
    specification.

    The `expected_output_data_body` should be set to a string equal to
    the body of the AMQP output message (i.e., the part of the input
    data that is expected to be extracted by the collector).

    The `additional_config_opts` is an optional attribute.  If the
    tested collector requires some non-standard configuration options,
    they should be provided here, as a dict, which will be appended to
    the standard (mocked) config.

    ***

    Ad variant I
    ------------

    The `raw_email` attribute should be set to a bytes string representing
    the whole input email message, in the original (raw) form.

    The `expected_mail_time` attribute should be set to a string equal to
    the expected value of the 'mail_time' meta header of the AMQP output
    message.

    ***

    Ad variant II
    -------------

    The `message_content` attribute should be set to an email message,
    without headers, and `expected_output_data_body` - to the part of
    the message that is expected to be extracted by the tested
    collector.

    The `email_subject` attribute should be set to specify the value of
    the 'Subject` e-mail header.

    The `email_items` attribute can be (optionally) overridden -- to
    change other e-mail header values.

    The `additional_headers` attribute can (optionally) be set, in
    order to provide additional e-mail headers (e.g. "Content-Type"),
    missing from the `_headers_pattern` attribute. They will be
    appended at the end of headers section, before the actual content.
    """

    _COLLECTOR_SOURCE = 'test'


    # * required common stuff (must be provided for each case)
    collector_class = None
    expected_source_channel = None
    expected_output_data_body = None

    # * optional common stuff (may be provided if needed)
    additional_config_opts = None

    # * required stuff related to Variant I (see the docstring above)
    raw_email = None
    expected_mail_time = None

    # * required+optional stuff related to Variant II (see the docstring above)
    _headers_pattern = (
        "Return-path: <{sender_user}@{sender_host}>\n"
        "Envelope-to: {recipient_user}@{recipient_host}\n"
        "Delivery-date: {datetime}\n"
        "Received: from {sender_user} by sender_host with local (Exim 4.84_2)\n"
        "\t(envelope-from <{sender_user}@{sender_host}>)\n"
        "\tid {id}\n"
        "\tfor {recipient_user}@{recipient_host}; {datetime}\n"
        "To: {recipient_user}@{recipient_host}\n"
        "Subject: {subject}\n"
        "Message-Id: <E1{id}@{sender_host}>\n"
        "From: {sender_user} <{sender_user}@{sender_host}>\n"
        "Date: {datetime}"
    )
    _input_dt_pattern = "%a, %d %b %Y %H:%M:%S %Z"
    message_content = None
    email_subject = None
    email_items = {
        'sender_user': 'test_sender',
        'sender_host': 'example.com',
        'recipient_user': 'test',
        'recipient_host': 'localhost',
        'datetime': 'Wed, 11 Jan 2017 02:05:12 UTC',
        'id': '1aBC23-000Tst-ff',
    }
    additional_headers = None


    def setUp(self):
        self.sample_email = self._get_sample_email()
        mock_stdin = self.patch('sys.stdin')
        mock_stdin.read.return_value = self.sample_email

        self.patch('n6.collectors.generic.QueuedBase.__init__', autospec=True, return_value=None)
        self.patch('n6.collectors.generic.CollectorConfigMixin.set_configuration')
        self.patch_object(self.collector_class, 'config', self._get_mocked_config(), create=True)

        self.init_kwargs = self.collector_class.get_script_init_kwargs()
        self.collector_instance = self.collector_class(**self.init_kwargs)

        input_data = self.collector_instance.input_data
        self.processed_data = self.collector_instance.process_input_data(**input_data)
        (self.output_rk,
         self.output_data_body,
         self.output_prop_kwargs) = self.collector_instance.get_output_components(**input_data)

    def _get_sample_email(self):
        if self.raw_email is not None:
            # Variant I
            assert self.expected_mail_time is not None, (
                '[Variant I] `raw_email` is provided '
                'so `expected_mail_time` should also be provided')
            assert self.email_subject is None, (
                '[Variant I] `raw_email` is provided '
                'so `email_subject` should *not* be provided')
            sample_email = self.raw_email
        else:
            # Variant II
            assert self.raw_email is None
            assert self.expected_mail_time is None, (
                '[Variant II] `raw_email` is not provided '
                'so `expected_mail_time` neither should be')
            assert self.email_subject is not None, (
                '[Variant II] `raw_email` is not provided '
                'so `email_subject` *should* be provided')
            sample_email = self._get_sample_email_for_variant_2()
        return sample_email

    def _get_sample_email_for_variant_2(self):
        formatted_headers = self._format_headers_for_variant_2()
        message_content = self._prepare_message_content_for_variant_2()
        if self.additional_headers:
            sample_email = '{headers}\n{additional}\n{content}'.format(
                headers=formatted_headers,
                additional=self.additional_headers,
                content=message_content)
        else:
            sample_email = '{headers}\n{content}'.format(
                headers=formatted_headers,
                content=message_content)
        return sample_email

    def _format_headers_for_variant_2(self):
        return self._headers_pattern.strip().format(subject=self.email_subject, **self.email_items)

    def _prepare_message_content_for_variant_2(self):
        message_content = self.message_content
        if message_content.split('\n', 1)[0].strip():
            # does not start with '\n' so we prepend it with one
            message_content = '\n' + message_content
        return message_content

    def _get_mocked_config(self):
        mocked_config = ConfigSection(mock.sentinel.section, {'source': self._COLLECTOR_SOURCE})
        if self.additional_config_opts is not None:
            mocked_config.update(self.additional_config_opts)
        return mocked_config


    def test_init_kwargs(self):
        self.assertEqual(self.init_kwargs, {'input_data': {'raw_email': self.sample_email}})


    def test_source_channel(self):
        source_channel = self.collector_instance.get_source_channel(**self.processed_data)
        self.assertEqual(source_channel, self.expected_source_channel)


    def test_output_rk(self):
        expected = '{}.{}'.format(self._COLLECTOR_SOURCE, self.expected_source_channel)
        version_tag = self.collector_instance.raw_format_version_tag
        if version_tag is not None:
            expected = '{}.{}'.format(expected, version_tag)
        self.assertEqual(self.output_rk, expected)


    def test_output_data_body(self):
        self.assertEqual(self.expected_output_data_body.strip(), self.output_data_body.strip())


    def test_output_prop_kwargs(self):
        self.assertIn('headers', self.output_prop_kwargs)
        self.assertIn('meta', self.output_prop_kwargs['headers'])
        meta_headers = self.output_prop_kwargs['headers']['meta']

        expected_mail_time = self.get_expected_mail_time()
        self.assertIn('mail_time', meta_headers)
        self.assertEqual(meta_headers['mail_time'], expected_mail_time)

        expected_mail_subject = self.get_expected_mail_subject()
        self.assertIn('mail_subject', meta_headers)
        self.assertEqual(meta_headers['mail_subject'], expected_mail_subject)

        expected_type = self.collector_instance.type
        self.assertEqual(self.output_prop_kwargs['type'], expected_type)

        expected_content_type = getattr(self.collector_instance, 'content_type', None)
        self.assertEqual(self.output_prop_kwargs.get('content_type'), expected_content_type)


    def get_expected_mail_time(self):
        if self.expected_mail_time is not None:
            # Variant I
            expected_mail_time = self.expected_mail_time
        else:
            # Variant II
            expected_mail_time = str(datetime_utc_normalize(datetime.datetime.strptime(
                self.email_items['datetime'],
                self._input_dt_pattern)))
        return expected_mail_time


    def get_expected_mail_subject(self):
        if self.raw_email is not None:
            # Variant I
            expected_email_subject_match = re.search(
                r'^Subject:\s*(.*?)\s*$',
                self.raw_email,
                re.IGNORECASE | re.MULTILINE)
            expected_mail_subject = expected_email_subject_match.group(1)
        else:
            # Variant II
            expected_mail_subject = self.email_subject
        # As in EmailMessage.get_subject()
        expected_mail_subject = ' '.join(expected_mail_subject.split())
        return expected_mail_subject

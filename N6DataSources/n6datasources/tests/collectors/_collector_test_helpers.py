# Copyright (c) 2017-2022 NASK. All rights reserved.

import collections
import itertools
import os
import os.path as osp
import queue
import unittest
import unittest.mock
import weakref
from argparse import ArgumentParser
from io import StringIO

from n6lib.class_helpers import FalseIfOwnerClassNameMatchesRegex
from n6lib.common_helpers import (
    PlainNamespace,
    reduce_indent,
)
from n6lib.config import Config
from n6lib.unit_test_helpers import TestCaseMixin



class BaseCollectorTestCase(TestCaseMixin, unittest.TestCase):

    # Prevent pytest *from treating* those subclasses of this class that
    # are base (abstract) classes *as concrete test classes*.
    __test__ = FalseIfOwnerClassNameMatchesRegex(r'\A_.*Base|\ABaseCollectorTestCase\Z')

    # These flags make it possible to turn on/off patching
    # of particular groups of stuff...
    patch_cmdline_args = True
    patch_config = True
    patch_LegacyQueuedBase = True
    patch_StatefulCollectorMixin = True


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._ArgumentParser_parse_known_args = ArgumentParser.parse_known_args

        # The following mock is used by `prepare_collector()` to patch the
        # `n6datapipeline.base.LegacyQueuedBase.publish_output()` method.
        # In subclasses this mock can be, e.g.:
        # * used in assertions (obviously!),
        # * reconfigured (e.g., by setting `side_effect` on it...),
        #   or even entirely replaced with something else.
        self.publish_output_mock = unittest.mock.MagicMock()

        # The following attribute will automatically be set to the state being
        # saved by a stub of the `StatefulCollectorMixin.save_state()` method
        # (if the latter is patched, using the stub, by `prepare_collector()`).
        # In actual tests (in subclasses) this attribute can be inspected to
        # check whether and what object has been passed in to `save_state()`.
        self.saved_state = unittest.mock.sentinel.NO_STATE


    # The following method is intended to be called in subclasses
    # (in their `test_*()` or `setUp()` methods).
    # Its functionality may be extended or modified in subclasses by:
    # * overriding the `patch_*` flags set above,
    # * extending (using super()...) this method directly,
    # * extending (using super()...) the `do_patching()` method defined
    #   below,
    # * extending (using super()...) the `do_patching_of_*()` methods
    #   defined below,
    # * extending/overriding the `make_*()` methods defined below.
    def prepare_collector(self,
                          collector_class,
                          config_content=None,
                          cmdline_args=(),
                          initial_state=unittest.mock.sentinel.NO_STATE,
                          additional_init_kwargs=None):

        self.do_patching(config_content, cmdline_args, initial_state)

        init_kwargs = collector_class.get_script_init_kwargs()
        if additional_init_kwargs is not None:
            init_kwargs = init_kwargs.copy()
            init_kwargs.update(additional_init_kwargs)
        collector = collector_class(**init_kwargs)

        return collector


    def do_patching(self,
                    config_content=None,
                    cmdline_args=(),
                    initial_state=unittest.mock.sentinel.NO_STATE):

        self.patch('n6lib.config.Config._load_n6_config_files',
                   self._get_unmemoized_classmethod__Config__load_n6_config_files())

        for patch_target in self.iter_targets_to_be_patched_as_unsupported():
            self.patch_with_plug(patch_target)

        if self.patch_cmdline_args:
            self.do_patching_of_cmdline_args(cmdline_args)
        if self.patch_config:
            self.do_patching_of_config(config_content)
        if self.patch_LegacyQueuedBase:
            self.do_patching_of_LegacyQueuedBase()
        if self.patch_StatefulCollectorMixin:
            self.do_patching_of_StatefulCollectorMixin(initial_state)


    def _get_unmemoized_classmethod__Config__load_n6_config_files(self):
        return classmethod(getattr(Config._load_n6_config_files.__func__,
                                   'func',
                                   Config._load_n6_config_files.__func__))


    def iter_targets_to_be_patched_as_unsupported(self):

        if self.patch_LegacyQueuedBase:
            # An explicit `NotImplementedError` will be raised if one of
            # these objects/methods is used by accident (it shouldn't as
            # anything that could cause that is faked/stubbed/mocked in
            # `do_patching_of_LegacyQueuedBase()`...).
            yield 'n6datapipeline.base.pika'
            yield 'n6datapipeline.base.LegacyQueuedBase.connect'


    def do_patching_of_cmdline_args(self, cmdline_args=()):
        self.patch_argparse_stuff(cmdline_args)


    def do_patching_of_config(self, config_content=None):
        fake_of__ConfigParser_read = self.make_fake_of__ConfigParser_read(config_content)
        stub_of__Config__get_config_file_paths = self.make_stub_of__Config__get_config_file_paths()

        self.patch(
            'configparser.ConfigParser.read',
            fake_of__ConfigParser_read,
            create=True)
        self.patch(
            'n6lib.config.Config._get_config_file_paths',
            stub_of__Config__get_config_file_paths)


    def do_patching_of_LegacyQueuedBase(self):
        (fake_of__LegacyQueuedBase___init__,
         fake_of__LegacyQueuedBase_run,
         fake_of__LegacyQueuedBase_stop,
         fake_of__LegacyQueuedBase_inner_stop,
        ) = self.make_fakes_of__LegacyQueuedBase_basic_methods()

        self.patch(
            'n6datapipeline.base.LegacyQueuedBase.__init__',
            fake_of__LegacyQueuedBase___init__)
        self.patch(
            'n6datapipeline.base.LegacyQueuedBase.run',
            fake_of__LegacyQueuedBase_run)
        self.patch(
            'n6datapipeline.base.LegacyQueuedBase.stop',
            fake_of__LegacyQueuedBase_stop)
        self.patch(
            'n6datapipeline.base.LegacyQueuedBase.inner_stop',
            fake_of__LegacyQueuedBase_inner_stop)
        self.patch(
            'n6datapipeline.base.LegacyQueuedBase.publish_output',
            self.publish_output_mock)


    def do_patching_of_StatefulCollectorMixin(self, initial_state=unittest.mock.sentinel.NO_STATE):
        stub_of__StatefulCollectorMixin_load_state = \
            self.make_stub_of__StatefulCollectorMixin_load_state(initial_state)
        stub_of__StatefulCollectorMixin_save_state = \
            self.make_stub_of__StatefulCollectorMixin_save_state()

        self.patch(
            'n6datasources.collectors.base.StatefulCollectorMixin.load_state',
            stub_of__StatefulCollectorMixin_load_state)
        self.patch(
            'n6datasources.collectors.base.StatefulCollectorMixin.save_state',
            stub_of__StatefulCollectorMixin_save_state)


    def make_fake_of__ConfigParser_read(self, config_content=None):

        adjusted_config_content = reduce_indent(config_content or '')

        def fake_of__ConfigParser_read(self, filenames, encoding=None):
            if isinstance(filenames, (str, bytes, os.PathLike)):
                filenames = [filenames]
            read_ok = []
            fp = StringIO(adjusted_config_content)
            for name in filenames:
                # (only for the first of filenames `fp` will offer any content)
                self.read_file(fp, name)
                if isinstance(name, os.PathLike):
                    name = os.fspath(name)
                read_ok.append(name)
            return read_ok

        return fake_of__ConfigParser_read


    def make_stub_of__Config__get_config_file_paths(self, *_filename_regexes):

        example_filename = 'we-are-just-testing-with-{}'.format(self.__class__.__qualname__)

        # noinspection PyDecorator
        @staticmethod
        def stub_of__Config__get_config_file_paths(path,
                                                   config_filename_regex=None,
                                                   config_filename_excluding_regex=None):
            return [osp.join(path, example_filename)]

        return stub_of__Config__get_config_file_paths


    def make_fakes_of__LegacyQueuedBase_basic_methods(self):

        # definitions of actual fakes

        def fake_of__LegacyQueuedBase___init__(self, **_):
            self.clear_amqp_communication_state_attributes()

            if self.input_queue is not None:
                raise NotImplementedError(
                    'support for testing collectors with non-None `input_queue` '
                    '(are there such ones?!) is not implemented')
            # (the invocation of `configure_pipeline()` is expected
            # to do nothing, since `self.input_queue` is None)
            self.configure_pipeline()
            _assert_is_none(self.input_queue)

            # (`self._conn_params_dict['heartbeat_interval']` has its
            # marginal use in the *iterative publishing* machinery)
            self._conn_params_dict = {'heartbeat_interval': 30}

        def fake_of__LegacyQueuedBase_run(self):
            self._connection = PlainNamespace(add_timeout=_add_timeout,
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

        def fake_of__LegacyQueuedBase_stop(self):
            self.inner_stop()

        def fake_of__LegacyQueuedBase_inner_stop(self):
            self._closing = True
            self.output_ready = False

        # internal helpers

        _assert_is_none = self.assertIsNone

        _timeout_callbacks = queue.PriorityQueue()
        _timeout_callbacks_priority_tie_breaker_gen = itertools.count()
        _pseudo_time = 0.0

        def _add_timeout(delay, callback):
            deadline = _pseudo_time + delay
            priority_tie_breaker = next(_timeout_callbacks_priority_tie_breaker_gen)
            _timeout_callbacks.put((deadline, priority_tie_breaker, callback))

        def _consume_timeout_callbacks():
            nonlocal _pseudo_time
            while True:
                try:
                    deadline, _, callback = _timeout_callbacks.get_nowait()
                except queue.Empty:
                    break
                _pseudo_time = deadline
                yield callback

        def _clear_timeout_callbacks():
            list(_consume_timeout_callbacks())

        return (fake_of__LegacyQueuedBase___init__,
                fake_of__LegacyQueuedBase_run,
                fake_of__LegacyQueuedBase_stop,
                fake_of__LegacyQueuedBase_inner_stop)


    def make_stub_of__StatefulCollectorMixin_load_state(
            self,
            initial_state=unittest.mock.sentinel.NO_STATE):

        if initial_state is unittest.mock.sentinel.NO_STATE:
            def stub_of__StatefulCollectorMixin_load_state(self):
                return self.make_default_state()
        else:
            def stub_of__StatefulCollectorMixin_load_state(self):
                return initial_state

        return stub_of__StatefulCollectorMixin_load_state


    def make_stub_of__StatefulCollectorMixin_save_state(self):

        test_case = weakref.proxy(self)

        def stub_of__StatefulCollectorMixin_save_state(self, state):
            test_case.saved_state = state

        return stub_of__StatefulCollectorMixin_save_state

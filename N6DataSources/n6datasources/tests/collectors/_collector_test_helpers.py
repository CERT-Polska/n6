# Copyright (c) 2017-2023 NASK. All rights reserved.

import collections
import dataclasses
import itertools
import os
import os.path as osp
import pickle
import queue
import re
import unittest
import unittest.mock
import weakref
from argparse import ArgumentParser
from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    Sequence,
)
from io import StringIO
from typing import (
    Optional,
    Union,
)

from unittest_expander import (
    expand,
    foreach,
    param,
    paramseq,
)

from n6datasources.collectors.base import BaseSimpleEmailCollector
from n6lib.class_helpers import FalseIfOwnerClassNameMatchesRegex
from n6lib.common_helpers import (
    PlainNamespace,
    reduce_indent,
)
from n6lib.config import Config
from n6lib.unit_test_helpers import (
    AnyInstanceOf,
    AnyMatchingRegex,
    TestCaseMixin,
)


class BaseCollectorTestCase(TestCaseMixin, unittest.TestCase):

    # Prevent pytest *from treating* those subclasses of this class that
    # are base (abstract) classes *as concrete test classes*.
    __test__ = FalseIfOwnerClassNameMatchesRegex(re.compile(r'''
        \A
        (?:
            Base
            .*
            CollectorTestCase
        |
            _
            .*
            Base
            (?:
                \Z
            |
                [^a-z]
            )
            .*
        )
        \Z''', re.VERBOSE))

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
                          *,
                          config_content=None,
                          cmdline_args=(),
                          stdin_data=None,
                          initial_state=unittest.mock.sentinel.NO_STATE,
                          additional_init_kwargs=None):

        self.do_patching(
            config_content=config_content,
            cmdline_args=cmdline_args,
            stdin_data=stdin_data,
            initial_state=initial_state)

        init_kwargs = collector_class.get_script_init_kwargs()
        if additional_init_kwargs is not None:
            init_kwargs = init_kwargs.copy()
            init_kwargs.update(additional_init_kwargs)
        collector = collector_class(**init_kwargs)

        return collector


    def do_patching(self,
                    *,
                    config_content=None,
                    cmdline_args=(),
                    stdin_data=None,
                    initial_state=unittest.mock.sentinel.NO_STATE):

        self.patch('n6lib.config.Config._load_n6_config_files',
                   self._get_unmemoized_classmethod__Config__load_n6_config_files())

        for patch_target in self.iter_targets_to_be_patched_as_unsupported():
            self.patch_with_plug(patch_target)

        if self.patch_cmdline_args:
            self.do_patching_of_cmdline_args(cmdline_args)
        if stdin_data is not None:
            self.do_patching_of_stdin(stdin_data)
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


    def do_patching_of_stdin(self, stdin_data):
        self.patch_stdin(stdin_data, encoding='utf-8', errors='surrogateescape')


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
            assert self.input_queue is None

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
                # In case we are dealing with a mutable object,
                # let's try to get a deep copy of it (to avoid some
                # kinds of bugs in tests...) and, also, let's make
                # collector tests automatically check that objects
                # declared as `initial state` can really be pickled
                # and unpickled. (Apart from that, note that this
                # stub of the `load_state()` method is supposed to
                # simulate unpickling the state from a file -- so
                # enforcing deep-copying of a mutable object seems
                # a good thing here.)
                pickled_and_unpickled = (
                    initial_state if initial_state is unittest.mock.sentinel.NO_STATE
                    else pickle.loads(pickle.dumps(
                        initial_state,
                        protocol=self._state_pickle_protocol)))
                if pickled_and_unpickled != initial_state:
                    # Such an inequality may be a symptom of a strange
                    # behavior of some engaged objects. Let's better do
                    # not pass that silently...
                    raise AssertionError(
                        f'this test helper machinery expects that the '
                        f'result of pickling and then unpickling the '
                        f'`initial_state` object is equal to it '
                        f'(whereas {pickled_and_unpickled=!a} is '
                        f'*not* equal to {initial_state=!a})')
                return pickled_and_unpickled

        return stub_of__StatefulCollectorMixin_load_state


    def make_stub_of__StatefulCollectorMixin_save_state(self):

        test_case = weakref.proxy(self)

        def stub_of__StatefulCollectorMixin_save_state(self, state):
            if state is not unittest.mock.sentinel.NO_STATE:
                # Let's make collector tests check that the state being
                # saved can really be pickled and unpickled correctly:
                state = pickle.loads(pickle.dumps(
                    state,
                    protocol=self._state_pickle_protocol))
            test_case.saved_state = state

        return stub_of__StatefulCollectorMixin_save_state


class BaseSimpleEmailCollectorTestCase(BaseCollectorTestCase):

    #
    # Stuff intended to be *defined* in concrete test classes
    #

    collector_class = unittest.mock.sentinel.not_set          # *required*
    collector_raw_type = unittest.mock.sentinel.not_set       # *required*
    collector_content_type = unittest.mock.sentinel.not_set   # *required* if `collector_raw_type`
                                                              # is not equal to "stream"

    collector_superclasses = (BaseSimpleEmailCollector,)      # *optional*

    @classmethod
    def cases(cls) -> Iterable[Union[
            'BaseSimpleEmailCollectorTestCase.SuccessCase',
            'BaseSimpleEmailCollectorTestCase.InitErrorCase',
            'BaseSimpleEmailCollectorTestCase.RunErrorCase',
        ]]:
        """
        *Required* to be implemented in concrete test classes -- as a
        class method returning a generator iterator (or another kind
        of iterable object) that yields instances of: `SuccessCase`,
        `InitErrorCase` and/or `RunErrorCase` -- which are classes
        available as attributes of `BaseSimpleEmailCollectorTestCase`.
        """
        raise NotImplementedError


    #
    # Stuff intended to be *used* in concrete test classes
    #

    @dataclasses.dataclass(frozen=True)
    class AutoExpectedPropKwargs:

        """
        A special placeholder object which can be used in place of the
        expected `publish_output()` call's 3rd argument (*prop kwargs*)
        -- see: `SuccessCase.expected_publish_output_calls`...
        """

        # Required arg/kwarg: a dictionary of the expected AMQP meta
        # headers (note that, typically, it will contain at least two
        # keys: "mail_subject" and "mail_time"), or `None` if no meta
        # headers are expected at all:
        expected_meta_headers: Union[dict, None]


    @dataclasses.dataclass(frozen=True)
    class SuccessCase:

        """For cases of successful collector runs."""

        # **Required args/kwargs**

        # * The configuration content for this case:
        config_content: str

        # * The input e-mail message in its raw form, including both
        #   headers and contents (note: it does not matter whether line
        #   endings in it are Unix-style `\n` or RFC-compliant `\r\n`,
        #   as -- whichever style you choose -- the test machinery
        #   will automatically prepare both variants and test them
        #   as separate cases; the only requirement related to line
        #   endings is that the chosen style needs to be applied
        #   consistently within whole `raw_email_msg`, i.e., you
        #   need to use either `\n` or `\r\n`, but not both):
        raw_email_msg: bytes

        # * A list of expected calls to collector's `publish_output()`.
        #   (*important*: expected calls' 3rd argument, *prop kwargs*,
        #   can be set to an instance of the `AutoExpectedPropKwargs`
        #   class -- which is a `BaseSimpleEmailCollectorTestCase`'s
        #   attribute, see above; then that `AutoExpectedPropKwargs`
        #   instance will be automatically replaced, separately for
        #   each test, with a dictionary containing necessary stuff):
        expected_publish_output_calls: Sequence[unittest.mock.call]

        # **Optional kwargs**

        # * A dict of `**kwargs` to be passed to `prepare_collector()`
        #   when preparing the collector instance to be tested
        #   (see `BaseCollectorTestCase.prepare_collector()`):
        additional_prepare_collector_kwargs: Optional[dict] = None

        # * A list of functions accepting the test instance (`self`)
        #   as the sole argument (they will be called directly *before*
        #   creation and initialization of the collector instance used
        #   in the test):
        before_init_callbacks: Sequence[Callable[['BaseSimpleEmailCollectorTestCase'], None]] = ()

        # * A list of functions accepting the test instance (`self`)
        #   as the sole argument (they will be called directly *after*
        #   creation and initialization of the collector instance used
        #   in the test; note: the collector instance will be available
        #   for them as `self.collector`):
        after_init_callbacks: Sequence[Callable[['BaseSimpleEmailCollectorTestCase'], None]] = ()

        # * The case label (may appear in generated test method names):
        label: Optional[str] = None


    @dataclasses.dataclass(frozen=True)
    class InitErrorCase:

        """For cases of errors from collector's `__init__()`."""

        # **Required args/kwargs**

        # * The configuration content for this case:
        config_content: str

        # * The input e-mail message in its raw form, including both
        #   headers and contents (note: it does not matter whether line
        #   endings in it are Unix-style `\n` or RFC-compliant `\r\n`,
        #   as -- whichever style you choose -- the test machinery
        #   will automatically prepare both variants and test them
        #   as separate cases; the only requirement related to line
        #   endings is that the chosen style needs to be applied
        #   consistently within whole `raw_email_msg`, i.e., you
        #   need to use either `\n` or `\r\n`, but not both):
        raw_email_msg: bytes

        # * The expected exception type:
        expected_exc_type: type[BaseException]

        # **Optional kwargs**

        # * The expected exception message regular expression:
        expected_exc_regex: Union[str, re.Pattern[str]] = ''

        # * A dict of `**kwargs` to be passed to `prepare_collector()`
        #   when preparing the collector instance to be tested
        #   (see `BaseCollectorTestCase.prepare_collector()`):
        additional_prepare_collector_kwargs: Optional[dict] = None

        # * A list of functions accepting the test instance (`self`)
        #   as the sole argument (they will be called directly *before*
        #   creation and initialization of the collector instance used
        #   in the test):
        before_init_callbacks: Sequence[Callable[['BaseSimpleEmailCollectorTestCase'], None]] = ()

        # * The case label (may appear in generated test method names):
        label: Optional[str] = None


    @dataclasses.dataclass(frozen=True)
    class RunErrorCase:

        """For cases of errors from collector's `run_collector()`."""

        # **Required args/kwargs**

        # * The configuration content for this case:
        config_content: str

        # * The input e-mail message in its raw form, including both
        #   headers and contents (note: it does not matter whether line
        #   endings in it are Unix-style `\n` or RFC-compliant `\r\n`,
        #   as -- whichever style you choose -- the test machinery
        #   will automatically prepare both variants and test them
        #   as separate cases; the only requirement related to line
        #   endings is that the chosen style needs to be applied
        #   consistently within whole `raw_email_msg`, i.e., you
        #   need to use either `\n` or `\r\n`, but not both):
        raw_email_msg: bytes

        # * The expected exception type:
        expected_exc_type: type[BaseException]

        # **Optional kwargs**

        # * The expected exception message regular expression:
        expected_exc_regex: Union[str, re.Pattern[str]] = ''

        # * A dict of `**kwargs` to be passed to `prepare_collector()`
        #   when preparing the collector instance to be tested
        #   (see `BaseCollectorTestCase.prepare_collector()`):
        additional_prepare_collector_kwargs: Optional[dict] = None

        # * A list of functions accepting the test instance (`self`)
        #   as the sole argument (they will be called directly *before*
        #   creation and initialization of the collector instance used
        #   in the test):
        before_init_callbacks: Sequence[Callable[['BaseSimpleEmailCollectorTestCase'], None]] = ()

        # * A list of functions accepting the test instance (`self`)
        #   as the sole argument (they will be called directly *after*
        #   creation and initialization of the collector instance used
        #   in the test; note: the collector instance will be available
        #   for them as `self.collector`):
        after_init_callbacks: Sequence[Callable[['BaseSimpleEmailCollectorTestCase'], None]] = ()

        # * The case label (may appear in generated test method names):
        label: Optional[str] = None


    #
    # Test machinery (no need to touch this stuff in subclasses)
    #

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__test__:
            expand(cls)


    @paramseq
    def _newline_rfc_compliance_cases(cls):
        yield param(with_rfc_compliant_newlines=True).label('with RFC-compliant line endings')
        yield param(with_rfc_compliant_newlines=False).label('with Unix-style line endings')


    @paramseq
    def _cases(cls):
        for case in cls.cases():
            case_param = param(case=case)
            if case.label:
                case_param = case_param.label(case.label)
            yield case_param


    @foreach(_newline_rfc_compliance_cases)
    @foreach(_cases)
    def test(self,
             case: Union[SuccessCase, InitErrorCase, RunErrorCase],
             with_rfc_compliant_newlines: bool):

        #
        # Test data checks and preparations

        assert isinstance(case, (self.SuccessCase,
                                 self.InitErrorCase,
                                 self.RunErrorCase)), (
            rf'Test machinery expectation is not satisfied! '
            rf'({type(case) = !a}, whereas a SuccessCase, '
            rf'InitErrorCase or RunErrorCase object was expected)')

        assert isinstance(case.raw_email_msg, bytes), (
            rf'Test machinery expectation is not satisfied! '
            rf'({type(case.raw_email_msg) = !a}, whereas a '
            rf'bytes object was expected)')

        if b'\r' in case.raw_email_msg:
            assert (case.raw_email_msg.count(b'\r\n')
                    == case.raw_email_msg.count(b'\r')
                    == case.raw_email_msg.count(b'\n')), (
                r"Test machinery expectation is not satisfied! "
                r"(`case.raw_email_msg` has unnormalized line endings, "
                r"whereas it should contain either only RFC-compliant "
                r"`\r\n` line endings or only Unix-style `\n` ones; then "
                r"our test machinery would be able to deal with it...)")

            # *is* RFC-compliant, so...
            raw_email_msg = (
                case.raw_email_msg                                 # ...keep it as-is
                if with_rfc_compliant_newlines
                else case.raw_email_msg.replace(b'\r\n', b'\n'))   # ...convert it to Unix-style
        else:
            # *is* Unix-style, so...
            raw_email_msg = (
                case.raw_email_msg.replace(b'\n', b'\r\n')         # ...convert it to RFC-compliant
                if with_rfc_compliant_newlines
                else case.raw_email_msg)                           # ...keep it as-is

        collector_prep_kwargs = dict(
            config_content=case.config_content,
            stdin_data=raw_email_msg,
            **(case.additional_prepare_collector_kwargs or {}))

        #
        # Actual test

        for superclass in self.collector_superclasses:
            assert issubclass(self.collector_class, superclass)

        for before_init in case.before_init_callbacks:
            before_init(self)

        if isinstance(case, self.InitErrorCase):
            with self.assertRaisesRegex(case.expected_exc_type, case.expected_exc_regex):
                self.prepare_collector(self.collector_class, **collector_prep_kwargs)
        else:
            self.collector = self.prepare_collector(self.collector_class, **collector_prep_kwargs)

            for after_init in case.after_init_callbacks:
                after_init(self)

            for superclass in self.collector_superclasses:
                assert isinstance(self.collector, superclass)
            assert isinstance(self.collector, self.collector_class)
            assert self.collector.raw_type == self.collector_raw_type
            if self.collector_raw_type == 'stream':
                assert self.collector.content_type is None
            else:
                assert self.collector.content_type == self.collector_content_type

            if isinstance(case, self.RunErrorCase):
                with self.assertRaisesRegex(case.expected_exc_type, case.expected_exc_regex):
                    self.collector.run_collection()
            else:
                self.collector.run_collection()

                expected_publish_output_calls = list(self._gen_expected_publish_output_calls(case))
                assert self.publish_output_mock.mock_calls == expected_publish_output_calls


    def _gen_expected_publish_output_calls(self,
                                           case: SuccessCase,
                                           ) -> Iterator[tuple]:  # (a *call* is a kind of tuple)

        for call in case.expected_publish_output_calls:
            # Note: an object returned from a `call(...)` invocation
            # behaves much like an ordinary 3-tuple.
            assert len(call) == 3, (
                rf'Test machinery expectation is not satisfied! '
                rf'(unsupported kind of call; {call = !a})')

            name, args, kwargs = call
            assert name == '', (
                rf"Test machinery expectation is not satisfied! (the "
                rf"mocked call's name should be empty; {name = !a})")

            if len(args) > 2 and isinstance(args[2], self.AutoExpectedPropKwargs):
                expected_prop_kwargs = self._make_real_expected_prop_kwargs(args[2])
                args = args[:2] + (expected_prop_kwargs,) + args[3:]

            yield call(*args, **kwargs)


    def _make_real_expected_prop_kwargs(self,
                                        auto_placeholder: AutoExpectedPropKwargs,
                                        ) -> dict:
        expected_prop_kwargs = {
            'timestamp': AnyInstanceOf(int),
            'message_id': AnyMatchingRegex(r'\A[0-9a-f]{32}\Z'),
            'headers': {},
            'type': self.collector_raw_type,
        }
        if self.collector_raw_type != 'stream':
            expected_prop_kwargs['content_type'] = self.collector_content_type

        if auto_placeholder.expected_meta_headers is not None:
            expected_prop_kwargs['headers']['meta'] = {}
            expected_prop_kwargs['headers']['meta'].update(auto_placeholder.expected_meta_headers)

        return expected_prop_kwargs

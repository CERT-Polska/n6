# Copyright (c) 2013-2021 NASK. All rights reserved.

"""
Collector base classes + auxiliary tools.
"""

import contextlib
import datetime
import pickle
import hashlib
import os
import sys
import time
from math import trunc
from typing import Optional

import requests

from n6lib.config import (
    ConfigError,
    ConfigMixin,
    ConfigSection,
)
from n6datapipeline.base import LegacyQueuedBase
from n6lib.class_helpers import attr_required
from n6lib.common_helpers import (
    AtomicallySavedFile,
    as_bytes,
    make_exc_ascii_str,
)
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)


#
# Mixin classes

class CollectorConfigMixin(ConfigMixin):

    def get_config_spec_format_kwargs(self):
        return {}

    def set_configuration(self):
        if self.is_config_spec_or_group_declared():
            self.config = self.get_config_section(**self.get_config_spec_format_kwargs())
        else:
            # backward-compatible behavior needed by a few collectors
            # that have `config_group = None` and -- at the same
            # time -- no `config_spec`/`config_spec_pattern`
            self.config = ConfigSection('<no section declared>')


class CollectorWithStateMixin(object):

    """
    Mixin for tracking state of an inheriting collector.

    Any picklable object can be saved as a state and then be retrieved
    as an object of the same type.
    """

    pickle_protocol = pickle.HIGHEST_PROTOCOL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_file_path = os.path.join(os.path.expanduser(
            self.config['cache_dir']), self.get_cache_file_name())

    def load_state(self):
        """
        Load collector's state from cache.

        Returns:
            Unpickled object of its original type.
        """
        try:
            with open(self._cache_file_path, 'rb') as cache_file:
                state = pickle.load(cache_file)
        except (OSError, ValueError, EOFError) as exc:
            state = self.make_default_state()
            LOGGER.warning(
                "Could not load state (%s), returning: %r",
                make_exc_ascii_str(exc),
                state)
        else:
            LOGGER.info("Loaded state: %r", state)
        return state

    def save_state(self, state):
        """
        Save any picklable object as a collector's state.

        Args:
            `state`: a picklable object.
        """
        cache_dir = os.path.dirname(self._cache_file_path)
        try:
            os.makedirs(cache_dir, 0o700)
        except OSError:
            pass

        with AtomicallySavedFile(self._cache_file_path, 'wb') as f:
             pickle.dump(state, f, self.pickle_protocol)
        LOGGER.info("Saved state: %r", state)

    def get_cache_file_name(self):
        source_channel = self.get_source_channel()
        source = self.get_source(source_channel=source_channel)
        return '{}.{}.pickle'.format(source, self.__class__.__name__)

    def make_default_state(self):
        return None


#
# Base classes

class AbstractBaseCollector(object):

    """
    Abstract base class for a collector script implementations.
    """

    @classmethod
    def run_script(cls):
        with logging_configured():
            init_kwargs = cls.get_script_init_kwargs()
            collector = cls(**init_kwargs)  # noqa
            collector.run_handling()

    @classmethod
    def get_script_init_kwargs(cls):
        """
        A class method: get a dict of kwargs for instantiation in a script.

        The default implementation returns an empty dict.
        """
        return {}

    #
    # Permanent (daemon-like) processing

    def run_handling(self):
        """
        Run the event loop until Ctrl+C is pressed.
        """
        try:
            self.run()
        except KeyboardInterrupt:
            self.stop()

    #
    # Abstract methods (must be overridden)

    def run(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


class BaseCollector(CollectorConfigMixin, LegacyQueuedBase, AbstractBaseCollector):

    """
    The standard "root" base class for collectors.
    """

    output_queue = {
        'exchange': 'raw',
        'exchange_type': 'topic',
    }

    # None or a string being the tag of the raw data format version
    # (can be set in a subclass)
    raw_format_version_tag = None

    # the name of the config group
    # (it does not have to be implemented if one of the `config_spec`
    # or the `config_spec_pattern` attribute is set in a subclass,
    # containing a declaration of exactly *one* config section)
    config_group = None

    # a sequence of required config fields (can be extended in
    # subclasses; typically, 'source' should be included there!)
    config_required = ('source',)
    # (NOTE: the `source` setting value in the config is only
    # the first part -- the `label` part -- of the actual
    # source specification string '<label>.<channel>')

    # must be set in a subclass (or its instance)
    # should be one of: 'stream', 'file', 'blacklist'
    # (note that this is something completely *different* than
    # <parser class>.event_type and <RecordDict instance>['type'])
    type = None
    limits_type_of = ('stream', 'file', 'blacklist')

    # the attribute has to be overridden, if a component should
    # accept the "--n6recovery" argument option and inherits from
    # the `BaseCollector` class or its subclass
    supports_n6recovery = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ### CR: use decorator n6lib.class_helpers.attr_required instead of:
        if self.type is None:
            raise NotImplementedError("attribute 'type' is not set")
        self.set_configuration()
        self._validate_type()

    @classmethod
    def get_script_init_kwargs(cls):
        """
        A class method: get a dict of kwargs for instantiation in a script.

        The default implementation returns an empty dict.
        """
        return {}

    def get_component_group_and_id(self):
        return 'collectors', self.__class__.__name__

    def make_binding_keys(self, binding_keys, *args):
        """
        Make binding keys for the collector using values from
        the pipeline config, if the collector accepts input messages
        (it has its `input_queue` class attribute implemented).

        Unlike in case of standard components (e.g., 'utils' group),
        values for the collector in the pipeline config are treated
        as target binding keys, not binding states.

        Each value from the config is the new binding key.

        Use the lowercase collector's class' name as associated option
        in the pipeline config, or its group's name - 'collectors'.

        Args:
            New binding keys as a list.
        """
        self.input_queue['binding_keys'] = binding_keys
        self.set_queue_name()

    def set_queue_name(self):
        """
        If the collector's `input_queue` dict does not have
        the `queue_name` key set, its queue's name defaults
        to the lowercase name of its class.

        The method may be called only for non-standard collectors
        accepting input messages.
        """
        if 'queue_name' not in self.input_queue or not self.input_queue['queue_name']:
            self.input_queue['queue_name'] = self.__class__.__name__.lower()

    def _validate_type(self):
        """Validate type of message, should be one of: 'stream', 'file', 'blacklist."""
        if self.type not in self.limits_type_of:
            raise Exception('Wrong type of archived data in mongo: {0},'
                            '  should be one of: {1}'.format(self.type, self.limits_type_of))

    def update_connection_params_dict_before_run(self, params_dict):
        """
        For some collectors there may be a need to override the standard
        AMQP heartbeat interval (e.g., when collecting large files...).
        """
        super().update_connection_params_dict_before_run(params_dict)
        if 'heartbeat_interval' in self.config:
            params_dict['heartbeat_interval'] = self.config['heartbeat_interval']

    #
    # Permanent (daemon-like) processing

    def run_handling(self):
        """
        Run the event loop until Ctrl+C is pressed.
        """
        try:
            self.run()
        except KeyboardInterrupt:
            self.stop()

    ### XXX: shouldn't the above method be rather:
    # def run_handling(self):
    #     """
    #     Run the event loop until Ctrl+C is pressed or other fatal exception.
    #     """
    #     try:
    #         self.run()
    #     except:
    #         self.stop()  # XXX: additional checks that all data have been sent???
    #         raise
    ### (or maybe somewhere in run_script...)
    ### (+ also for all other components?)

    #
    # Input data processing -- preparing output data

    def get_output_components(self, **input_data):
        """
        Get source specification string, AMQP message body and AMQP headers.

        Kwargs:
            Some keyword-only arguments suitable
            for the process_input_data() method.

        Returns:
            A tuple of positional arguments for the publish_output() method:
            (<routing key (string)>,
             <actual data body (bytes)>,
             <custom keyword arguments for pika.BasicProperties (dict)>).

        This is a "template method" -- calling the following overridable
        methods:

        * process_input_data(),
        * get_source_channel(),
        * get_source(),
        * get_output_rk(),
        * get_output_data_body(),
        * get_output_prop_kwargs().

        NOTE: get_source_channel() and get_output_data_body() are abstract
        methods. You need to implement them in a subclass to be able to call
        this method.
        """
        processed_data = self.process_input_data(**input_data)
        source_channel = self.get_source_channel(**processed_data)
        source = self.get_source(
                source_channel=source_channel,
                **processed_data)
        output_rk = self.get_output_rk(
                source=source,
                **processed_data)
        output_data_body = self.get_output_data_body(
                source=source,
                **processed_data)
        output_prop_kwargs = self.get_output_prop_kwargs(
                source=source,
                output_data_body=output_data_body,
                **processed_data)
        return output_rk, output_data_body, output_prop_kwargs

    def process_input_data(self, **input_data):
        """
        Preproccess input data.

        Kwargs:
            Input data as some keyword arguments.

        Returns:
            A dict of additional keyword arguments for the following methods:

            * get_source_channel(),
            * get_source(),
            * get_output_rk(),
            * get_output_data_body(),
            * get_output_prop_kwargs().

        Typically, this method is used indirectly -- being called in
        get_output_components().

        The default implementation of this method does nothing and returns
        the given input data unchanged.
        """
        return input_data

    # NOTE: typically, this method must be implemented in concrete subclasses
    def get_source_channel(self, **processed_data):
        """
        Get the "channel" part of source specification.

        Kwargs:
            Processed data (as returned by the process_input_data() method)
            passed as keyword arguments (to be specified in subclasses).

        Returns:
            The "channel" part of source specification as a string.

        Typically, this method is used indirectly -- being called in
        get_output_components().

        In BaseCollector, this is a method placeholder; if you want to call
        the get_output_components() method you *need* to implement this
        method in your subclass.
        """
        raise NotImplementedError

    def get_source(self, source_channel, **processed_data):
        """
        Get the source specification string.

        Kwargs:
            `source_channel` (a string):
                The "channel" part of the source specification.
            <some keyword arguments>:
                Processed data (as returned by the process_input_data()
                method) passed as keyword arguments (the default
                implementation ignores them).

        Returns:
            A string based on pattern: '<source label>.<source channel>'.

        Typically, this method is used indirectly -- being called in
        get_output_components().

        The default implementation of this method should be sufficient in
        most cases.
        """
        return '{0}.{1}'.format(self.config['source'],
                                source_channel)

    def get_output_rk(self, source, **processed_data):
        """
        Get the output AMQP routing key.

        Kwargs:
            `source`:
                The source specification string (based on pattern:
                '<source label>.<source channel>').
            <some keyword arguments>:
                Processed data (as returned by the process_input_data()
                method) passed as keyword arguments (the default
                implementation ignores them).

        Returns:
            The output AMQP routing key (a string).

        Typically, this method is used indirectly -- being called in
        get_output_components().

        The default implementation of this method should be sufficient in
        most cases.
        """
        if self.raw_format_version_tag is None:
            return source
        else:
            return '{0}.{1}'.format(source, self.raw_format_version_tag)

    # NOTE: typically, this method must be implemented in concrete subclasses
    def get_output_data_body(self, source, **processed_data):
        """
        Get the output AMQP message data.

        Kwargs:
            `source`:
                The source specification string (based on pattern:
                '<source label>.<source channel>').
            <some keyword arguments>:
                Processed data (as returned by the process_input_data()
                method) passed as keyword arguments (to be specified in
                subclasses).

        Returns:
            The output AMQP message body (a bytes object).

        Typically, this method is used indirectly -- being called in
        get_output_components().

        In BaseCollector, this is a method placeholder; if you want to call
        the get_output_components() method you *need* to implement this
        method in your subclass.
        """
        raise NotImplementedError

    def get_output_prop_kwargs(self, source, output_data_body,
                               **processed_data):
        """
        Get a dict of custom keyword arguments for pika.BasicProperties.

        Kwargs:
            `source`:
                The source specification string (based on pattern:
                '<source label>.<source channel>').
            `output_data_body` (bytes):
                The output AMQP message data (as returned by the
                get_output_data_body() method).
            <some keyword arguments>:
                Processed data (as returned by the process_input_data()
                method) passed as keyword arguments (the default
                implementation ignores them).

        Returns:
            Custom keyword arguments for pika.BasicProperties (a dict).

        Typically, this method is used indirectly -- being called in
        get_output_components().

        The default implementation of this method provides the following
        properties: 'message_id', 'type', 'headers'. The method can be
        *extended* in subclasses (with cooperative super()).

        """
        created_timestamp = trunc(time.time())
        message_id = self.get_output_message_id(
                    source=source,
                    created_timestamp=created_timestamp,
                    output_data_body=output_data_body,
                    **processed_data)

        properties = {
            'message_id': message_id,
            'type': self.type,
            'timestamp': created_timestamp,
            'headers': {},
        }

        if self.type in ('file', 'blacklist'):
            try:
                properties.update({'content_type': self.content_type})
            except AttributeError as exc:
                LOGGER.critical("Type file or blacklist must set content_type attribute : %r", exc)
                raise

        return properties

    def get_output_message_id(self, source, created_timestamp,
                              output_data_body, **processed_data):
        """
        Get the output message id (aka `rid`).

        Kwargs:
            `source`:
                The source specification string (based on pattern:
                '<source label>.<source channel>').
            `output_data_body`:
                The output AMQP message body (bytes) as returned by the
                get_output_data_body() method.
            `created_timestamp`:
                Message creation timestamp as an int number.
            <some keyword arguments>:
                Processed data (as returned by the process_input_data()
                method) passed as keyword arguments (the default
                implementation ignores them).

        Returns:
            The output message id (a string).

        Typically, this method is used indirectly -- being called in
        get_output_prop_kwargs() (which is called in get_output_components()).

        The default implementation of this method should be sufficient in
        most cases.
        """
        components = (
            as_bytes(source),
            as_bytes('{0:d}'.format(created_timestamp)),
            output_data_body,
        )
        hashed_bytes = b'\0'.join(components)
        return hashlib.md5(hashed_bytes, usedforsecurity=False).hexdigest()


class BaseOneShotCollector(BaseCollector):

    """
    The main base class for one-shot collectors (e.g. cron-triggered ones).
    """

    def __init__(self, input_data=None, **kwargs):
        """
        Kwargs:
            `input_data` (optional):
                A dict of keyword arguments for the get_output_components()
                method.
        """
        super().__init__(**kwargs)
        self.input_data = (input_data if input_data is not None
                           else {})
        self._output_components = None

    def run_handling(self):
        """
        For one-shot collectors: handle an event and return immediately.
        """
        self._output_components = self.get_output_components(**self.input_data)
        self.run()
        LOGGER.info('Stopped')

    def start_publishing(self):
        # TODO: docstring or comment what is being done here...
        self.publish_output(*self._output_components)
        self._output_components = None
        LOGGER.debug('Stopping')
        self.inner_stop()


class BaseTimeOrderedRowsCollector(CollectorWithStateMixin, BaseCollector):

    """
    The base class for "row-like" data collectors.


    Implementation/overriding of methods and attributes:

    * required:
        * `obtain_orig_data()`
          -- see its docs,
        * `pick_raw_row_time()`
          -- see its docs (and the docs of `extract_row_time()`),
        * `clean_row_time()`
          -- see its docs (and the docs of `extract_row_time()`);
        
    * optional: see the attributes and methods defined within the body
      of this class below the "Stuff that can be overridden..." comment.


    Original data (as returned by `obtain_orig_data()`) should consist
    of rows that can be decoded from bytes and singled out (see:
    `all_rows_from_orig_data()` and the methods it calls), then selected
    (see: `get_fresh_rows_only()` and the methods it calls), and finally
    joined and encoded to bytes (see: `output_data_from_fresh_rows()`
    and the methods it calls).

    Rows (those for whom `should_row_be_used()` returns true) should
    contain the time/order field; its values are to be extracted by
    the `extract_row_time()` method; or -- let's be more specific --
    by certain methods called by it, namely: `pick_raw_row_time()`
    (which picks the raw time/order value from the given row) and
    `clean_row_time()` (which validates, converts and normalizes that
    time/order value).

    For example, for rows such as:

        '"123", "2019-07-18 14:29:05", "sample", "data"\n'
        '"987", "2019-07-17 15:13:13", "other", "data"\n'

    ...the `pick_raw_row_time()` should pick the values from the second
    column (for an example implementation -- see the docstring of the
    `pick_raw_row_time()` method).

    Values returned by `clean_row_time()` can have any form and type
    -- provided that a **newer** one always sorts as **greater than**
    an older one, and values representing the **same** time are always
    **equal**. An important related requirement is that the value returned
    by the `get_oldest_possible_row_time()` method **must always** sort
    as **less than** any value returned by `clean_row_time()`.

    It is important to highlight that the original data (rows) are
    expected to be already sorted **descendingly** (from newest to oldest)
    by the time/order field (as extracted with `extract_row_time()`,
    described above). If not, that must be enforced by your
    implementation, e.g., in the following way:

        def all_rows_from_orig_data(self, orig_data):
            all_rows = super().all_rows_from_orig_data(orig_data)
            return sorted(all_rows, key=self._row_sort_key, reverse=True)

        def _row_sort_key(self, row):
            sort_key = self.extract_row_time(row)
            if sort_key is None:
                sort_key = self.get_oldest_possible_row_time()
            return sort_key

    ***

    Even a more important requirement, concerning the data source itself,
    is that values of the *time/order* field of any **new** (fresh) rows
    encountered by the collector **must** be **greater than or equal to**
    the *time/order* field's values of all rows collected during any
    previous runs of the collector.

    If the **data source does not satisfy** this requirement then **some
    rows will be lost** (i.e., will **not** be collected at all).

    For example, let's assume that a certain data source provided
    the following data:

        '"3", "2019-07-19 02:00:00", "sample", "data"\n'
        '"2", "2019-07-18 01:00:00", "sample_data", "data"\n'
        '"1", "2019-07-17 00:00:00", "other_data", "data"\n'

    Assuming that our imaginary collector threats the second column
    as the *time/order* field and that we just ran our collector,
    all those rows have been collected by it and the collector's saved
    state points on the `3`-rd row as the recent one.

    Now, let's imagine that the source added three new rows -- so that
    the data provided by the source looks like this:

        '"6", "2019-07-20 02:00:00", "sample_2", "data"\n'
        '"5", "2019-07-18 02:00:00", "sample_1", "data"\n'
        '"4", "2019-07-21 02:00:00", "sample_3", "data"\n'
        '"3", "2019-07-19 02:00:00", "sample", "data"\n'
        '"2", "2019-07-18 01:00:00", "sample_data", "data"\n'
        '"1", "2019-07-17 00:00:00", "other_data", "data"\n'

    If we run our collector now, it will collect the `6`-th row, but it
    will **not** collect the `4`-th and `5`-th rows, because of treating
    the `5`-th one as a row *from the past* (because its *time/order*
    value is less (older) than the, previously-saved-as-the-recent-one,
    `3`-rd's one).

    Note that, in such a case, making our collector sort these rows
    by the *time/order* field would **not** help much:

        '"4", "2019-07-21 02:00:00", "sample_3", "data"\n'
        '"6", "2019-07-20 02:00:00", "sample_2", "data"\n'
        '"5", "2019-07-18 02:00:00", "sample_1", "data"\n'
        '"3", "2019-07-19 02:00:00", "sample", "data"\n'
        '"2", "2019-07-18 01:00:00", "sample_data", "data"\n'
        '"1", "2019-07-17 00:00:00", "other_data", "data"\n'

    Even though the `4`-th and `6`-th rows would be collected, the
    `5`-th one **would not** -- as it would be (still) considered a row
    *from the past*. Indeed, the main problem is with the data source
    itself: it does not satisfy the requirement described above.

    ***

    One more thing concerning the original input data: while it is OK
    to have several rows with exact same values of the time/order field,
    whole rows should not be the same (unless you do not care that such
    duplicates may be detected as already seen and, consequently,
    omitted).

    """

    config_required = ('source', 'cache_dir')

    _NEWEST_ROW_TIME_STATE_KEY = 'newest_row_time'
    _NEWEST_ROWS_STATE_KEY = 'newest_rows'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._state: Optional[dict] = None          # to be set in `run_handling()`
        self._output_data: Optional[bytes] = None   # to be set in `run_handling()` if needed

    def run_handling(self):
        self._state = self.load_state()
        orig_data = self.obtain_orig_data()
        all_rows = self.all_rows_from_orig_data(orig_data)
        fresh_rows = self.get_fresh_rows_only(all_rows)
        if fresh_rows:
            self._output_data = self.output_data_from_fresh_rows(fresh_rows)
            super().run_handling()

    def make_default_state(self):
        return {
            self._NEWEST_ROW_TIME_STATE_KEY: self.get_oldest_possible_row_time(),
            self._NEWEST_ROWS_STATE_KEY: set(),
        }

    def start_publishing(self):
        self.start_iterative_publishing()

    def publish_iteratively(self):
        rk, body, prop_kwargs = self.get_output_components(output_data=self._output_data)
        self.publish_output(rk, body, prop_kwargs)
        yield self.FLUSH_OUT
        self.save_state(self._state)

    def get_output_data_body(self, output_data, **kwargs):
        return output_data


    #
    # Stuff that can be overridden in subclasses (only if needed,
    # as sensible defaults are provided -- *except* for the three
    # abstract methods: `obtain_orig_data()`, `pick_raw_row_time()`
    # and `clean_row_time()`)

    # * basic raw event attributes:

    type = 'file'
    content_type = 'text/csv'

    # * stuff related to writable state management:

    def get_oldest_possible_row_time(self):
        """
        The value returned by this method should sort as *less than*
        any real row time returned by `clean_row_time()`.

        **Important:** when implementing your subclass, you need to
        ensure that the value returned by this method meets the above
        condition for any non-`None` value returned by `clean_row_time()`.

        The value returned by the default implementation of this method
        is `""` (empty `str`) -- appropriate for such implementations
        of `clean_row_time()` that produce ISO-8601-formatted strings.
        Note that for other implementations of `clean_row_time()` the
        appropriate value may be, for example, `datetime.datetime.min`
        or `0`...

        See also: the docs of the method `clean_row_time()` and the
        description of the return value of the method `extract_row_time()`
        (in its docs).
        """
        return ''

    # * obtaining original data:

    def obtain_orig_data(self) -> bytes:
        """
        Abstract method: obtain the original raw data and return it.

        Example implementation:

            return RequestPerformer.fetch(method='GET',
                                          url=self.config['url'],
                                          retries=self.config['download_retries'])

        (Though, in practice -- when it comes to obtaining original
        data with the `RequestPerformer` stuff -- you will more likely
        want to use the `BaseDownloadingTimeOrderedRowsCollector` class
        rather than to implement `RequestPerformer`-based `obtain_orig_data()`
        by your own.)

        """
        raise NotImplementedError

    # * decoding + splitting original data:

    def all_rows_from_orig_data(self, orig_data: bytes):
        decoded = self.decode_orig(orig_data)
        return self.split_orig(decoded)

    def decode_orig(self, orig_data: bytes):
        return orig_data.decode('utf-8', 'surrogateescape')

    def split_orig(self, decoded):
        return decoded.split('\n')

    # * re-joining + encoding output data:

    def output_data_from_fresh_rows(self, fresh_rows) -> bytes:
        joined = self.join_output(fresh_rows)
        return self.encode_output(joined)

    def join_output(self, fresh_rows):          # should be `split_orig()`'s reversion
        return '\n'.join(fresh_rows)

    def encode_output(self, joined) -> bytes:   # should be `decode_orig()`'s reversion
        return joined.encode('utf-8', 'surrogateescape')

    # * selection of fresh rows:

    def get_fresh_rows_only(self, all_rows):
        prev_newest_row_time = self._state[self._NEWEST_ROW_TIME_STATE_KEY]
        prev_newest_rows = self._state[self._NEWEST_ROWS_STATE_KEY]

        newest_row_time = None
        newest_rows = set()

        fresh_rows = []

        preceding_row_time = None

        for row in all_rows:
            row_time = self.extract_row_time(row)
            if row_time is None:
                continue

            # it is required that time values in consecutive rows are
            # non-increasing and monotonic (but can be repeating)
            if preceding_row_time is not None and row_time > preceding_row_time:
                raise ValueError(
                    'encountered row time {!r} > preceding row time {!r}'.format(
                        row_time,
                        preceding_row_time))
            preceding_row_time = row_time

            if row_time < prev_newest_row_time:
                # stop collecting when reached rows which are old enough
                # that we are sure they must have already been collected
                break

            if newest_row_time is None:
                # this is the first (newest) actual (not blank/commented)
                # row in the downloaded file -- so here we have the *newest*
                # row time
                newest_row_time = row_time

            if row_time == newest_row_time:
                # this row is amongst those with the *newest* row time
                newest_rows.add(row)

            if row in prev_newest_rows:
                # this row is amongst those with the *previously newest*
                # row time, *and* we know that it has already been
                # collected -> so we *skip* it
                assert row_time == prev_newest_row_time
                continue

            # this row have *not* been collected yet -> let's collect it
            # now (in its original form, i.e., without any modifications)
            fresh_rows.append(row)

        if fresh_rows:
            self._state[self._NEWEST_ROW_TIME_STATE_KEY] = newest_row_time
            self._state[self._NEWEST_ROWS_STATE_KEY] = newest_rows

            # sanity assertions
            fresh_newest_rows = newest_rows - prev_newest_rows
            assert newest_row_time is not None and fresh_newest_rows
        else:
            # sanity assertions
            assert (newest_row_time is None and not newest_rows
                    or
                    newest_row_time == prev_newest_row_time and newest_rows == prev_newest_rows)

        return fresh_rows


    def extract_row_time(self, row):
        """
        Extract the row time indicator from the given row.

        Args:
            `row`:
                An item yielded by an iterable returned by
                `all_rows_from_orig_data()`.

        Returns:
            *Either* `None` -- indicating that `row` should just be
            ignored (skipped); *or* a sortable date/time value, i.e.,
            an object that represents the date or timestamp extracted
            from `row`, e.g., an ISO-8601-formatted string (that
            represents some date or date+time), or a `float`/`int`
            value being a UNIX timestamp, or a `datetime.datetime`
            instance; its type does not matter -- provided that such
            values (returned by this method, and also by the method
            `get_oldest_possible_row_time()`) sort in a sensible way:
            a newer one is always greater than an older one, and values
            representing the same time are always equal.

        This is a template method that calls the following methods:

        * `should_row_be_used()` (has a sensible default implementation
          but, of course, can be overridden/extended in your subclass
          if needed) -- takes the given `row` and returns a boolean
          value; if a false value is returned, the result of the whole
          `extract_row_time()` call will be `None`, and calls of the
          further methods (that is, of `pick_raw_row_time()` and
          `clean_row_time()`) will *not* be made;

        * `pick_raw_row_time()` (must be implemented in subclasses)
          -- takes the given `row` and extracts the raw value of its
          date-or-timestamp field, and then returns that raw value
          (typically, as a string); alternatively it can return `None`
          (to indicate that the whole row should be ignored) -- then
          the result of the whole `extract_row_time()` call will also
          be `None`, and the call of `clean_row_time()` will *not* be
          made;

        * `clean_row_time()` (must be implemented in subclasses) --
          takes the value just returned by `pick_raw_row_time()` and
          cleans it (i.e., validates and normalizes -- in particular,
          converts to some target type, if needed), and then returns
          the cleaned value; alternatively it can return `None` (to
          indicate that the whole row should be ignored); the returned
          value will become the result of the whole `extract_row_time()`
          call.
        """
        if not self.should_row_be_used(row):
            return None
        raw_row_time = self.pick_raw_row_time(row)
        if raw_row_time is None:
            return None
        return self.clean_row_time(raw_row_time)

    def should_row_be_used(self, row):
        """
        See the docs of `extract_row_time()`.

        The default implementation of this method returns `False` if
        the given `row` starts with the `#` character or contains only
        whitespace characters (or no characters at all); otherwise the
        returned value is `True`.
        """
        return row.strip() and not row.startswith('#')

    def pick_raw_row_time(self, row):
        """
        Abstract method; see the docs of `extract_row_time()`.

        Below we present an implementation for a case when data rows
        are expected to be formatted according to the following pattern:
        `"<row number>","<row date+time>",<other data fields...>`.

            def pick_raw_row_time(self, row):
                # (here we use `extract_field_from_csv_row()` --
                # imported from `n6lib.csv_helpers`)
                return extract_field_from_csv_row(row, column_index=1)

        An alternative version of the above example:

            def pick_raw_row_time(self, row):
                # Here we return `None` if an error occurs when trying
                # to parse the row -- because:
                # * we assume that (for our particular data source)
                #   some wrongly formatted rows may appear,
                # * and we want to skip such rows.
                try:
                    return extract_field_from_csv_row(row, column_index=1)
                except Exception as exc:
                    LOGGER.warning(
                        'Cannot extract the time field from the %r row '
                        '(%r) -- so the row will be skipped.', row, exc)
                    return None
        """
        raise NotImplementedError

    def clean_row_time(self, raw_row_time):
        """
        Abstract method; see the docs of `extract_row_time()`.

        An example implementation for a case when `raw_row_time` is
        expected to be an ISO-8601-formatted date+time indicator --
        such as `"2020-01-23T19:52:17+01:00"`:

            def clean_row_time(self, raw_row_time):
                # (here we use `parse_iso_datetime_to_utc()` --
                # imported from `n6lib.datetime_helpers`)
                return str(parse_iso_datetime_to_utc(raw_row_time))

        An alternative version of the above example:

            def clean_row_time(self, raw_row_time):
                # Here we return `None` if a conversion error occurs
                # -- because:
                # * we assume that (for our particular data source)
                #   rows containing wrongly formatted time indicators
                #   may appear,
                # * and we want to skip such rows.
                try:
                    return str(parse_iso_datetime_to_utc(raw_row_time))
                except ValueError:
                    LOGGER.warning(
                        'Cannot parse %r as an ISO date+time so the row '
                        'containing it will be skipped.', raw_row_time)
                    return None

        **Important:** the resultant value, if not `None`, must be
        compatible, in terms of sorting, with the value returned by
        `get_oldest_possible_row_time()` (see its docs, as well as the
        return value description in the docs of `extract_row_time()`).
        """
        raise NotImplementedError


class BaseDownloadingCollector(BaseCollector):

    # This constant is used only if neither config files nor
    # defaults in the config spec (if any) provide the value
    # of the `download_retries` option.
    DEFAULT_DOWNLOAD_RETRIES_IF_NOT_SPECIFIED = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._http_response = None          # to be set in request_performer()
        self._http_last_modified = None     # to be set in request_performer()

    @property
    def http_response(self) -> Optional[requests.Response]:
        return self._http_response

    @property
    def http_last_modified(self) -> Optional[datetime.datetime]:
        return self._http_last_modified

    def download(self, *args, stream=False, **kwargs) -> bytes:
        with self.request_performer(*args, stream=stream, **kwargs) as perf:
            return perf.response.content

    def download_text(self, *args, stream=False, **kwargs) -> str:
        with self.request_performer(*args, stream=stream, **kwargs) as perf:
            return perf.response.text

    @contextlib.contextmanager
    def request_performer(self,
                          url: str,
                          method: str = 'GET',
                          retries: Optional[int] = None,
                          custom_request_headers: Optional[dict] = None,
                          **rest_performer_constructor_kwargs):
        retries = self._get_request_retries(retries)
        headers = self._get_request_headers(custom_request_headers)
        with RequestPerformer(method=method,
                              url=url,
                              retries=retries,
                              headers=headers,
                              **rest_performer_constructor_kwargs) as perf:
            self._http_response = perf.response
            self._http_last_modified = perf.get_dt_header('Last-Modified')
            yield perf

    def _get_request_retries(self, retries: Optional[int]) -> int:
        if retries is None:
            retries = int(self.config.get('download_retries',
                                          self.DEFAULT_DOWNLOAD_RETRIES_IF_NOT_SPECIFIED))
        return retries

    def _get_request_headers(self, custom_request_headers: Optional[dict]) -> dict:
        base_request_headers = self.config.get('base_request_headers', {})
        if not isinstance(base_request_headers, dict):
            raise ConfigError('config option `base_request_headers` '
                              'is not a dict: {!r}'.format(base_request_headers))
        headers = base_request_headers.copy()
        if custom_request_headers:
            headers.update(custom_request_headers)
        return headers

    def get_output_prop_kwargs(self, **processed_data) -> KwargsDict:
        prop_kwargs = super().get_output_prop_kwargs(**processed_data)
        if self.http_last_modified:
            prop_kwargs['headers'].setdefault('meta', dict())
            prop_kwargs['headers']['meta']['http_last_modified'] = str(self.http_last_modified)
        return prop_kwargs


class BaseDownloadingTimeOrderedRowsCollector(BaseDownloadingCollector,
                                              BaseTimeOrderedRowsCollector):

    source_config_section = None

    config_spec_pattern = '''
        [{source_config_section}]
        source :: str
        cache_dir :: str
        url :: str
        download_retries = 10 :: int
        base_request_headers = {{}} :: py
    '''

    @attr_required('source_config_section')
    def get_config_spec_format_kwargs(self) -> KwargsDict:
        return {'source_config_section': self.source_config_section}

    def obtain_orig_data(self) -> bytes:
        return self.download(self.config['url'])


#
# Entry point factory

def add_collector_entry_point_functions(module):
    if isinstance(module, str):
        module = sys.modules[module]
    for name in dir(module):
        if not name.startswith('_'):
            obj = getattr(module, name)
            is_collector_class = isinstance(obj, type) and issubclass(obj, AbstractBaseCollector)
            if is_collector_class:
                assert hasattr(obj, 'run_script')
                setattr(module, f'{name}_main', obj.run_script)

# Copyright (c) 2013-2023 NASK. All rights reserved.

"""
Parser base classes + auxiliary tools.
"""

import dataclasses
import hashlib
import io
import sys
from datetime import datetime
from typing import SupportsBytes

import pika

from n6datapipeline.base import LegacyQueuedBase
from n6lib.class_helpers import attr_required
from n6lib.common_helpers import (
    FilePagedSequence,
    as_bytes,
    ascii_str,
    make_exc_ascii_str,
    picklable,
)
from n6lib.config import (
    Config,
    ConfigMixin,
    ConfigSection,
    as_config_spec_string,
    combined_config_spec,
)
from n6lib.csv_helpers import csv_string_io
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger, logging_configured
from n6lib.record_dict import (
    AdjusterError,
    RecordDict,
    BLRecordDict,
)
from n6lib.typing_helpers import KwargsDict


LOGGER = get_logger(__name__)

MAX_IPS_IN_ADDRESS = 63


# TODO: finish tests
class BaseParser(ConfigMixin, LegacyQueuedBase):

    """
    The "root" base class for parsers.
    """

    # these attributes are default base for actual instance attributes
    # `input_queue` and `output_queue` (see `LegacyQueuedBase.__new__()`
    # + see below: the comment concerning the `default_binding_key`
    # class attribute)
    input_queue = {
        "exchange": "raw",
        "exchange_type": "topic",
    }
    output_queue = {
        "exchange": "event",
        "exchange_type": "topic",
    }

    # a string in one of the formats:
    #    '<source provider>.<source channel>' or
    #    '<source provider>.<source channel>.<raw format version tag>'
    # to be, typically, used as the input queue's *binding key* and *name*
    # (*should* be set in subclasses because the standard implementations
    # of the `preinit_hook()` and `configure_pipeline()` methods make use
    # of it)
    default_binding_key = None

    # a dict of default items for each resultant record dict
    # (it can be left as None)
    constant_items = None

    # the default config spec pattern for parsers; it can be overridden
    # in subclasses, but note that the default implementation of the
    # `set_configuration()` method expects that the *config spec
    # pattern* includes the `{parser_class_name}` section -- treated
    # by that method as the *main section*; also, the `prefetch_count`
    # option (with the `int` converter) should be declared in the
    # *main section*; *hint:* values of the attribute declared along
    # the inheritance hierarchy can be easily *combined* (in a
    # cooperative-inheritance-friendly way) by using the
    # `n6lib.config.combined_config_spec()` helper
    config_spec_pattern = combined_config_spec('''
        [{parser_class_name}]

        prefetch_count = 1 :: int
    ''')

    # instance attributes to be set automatically
    # when `set_configuration()` is called
    config: ConfigSection   # containing options from the *main section*
    config_full: Config     # containing *all* declared config sections

    # a record dict class -- n6lib.record_dict.RecordDict or its subclass
    # (can be overridden in subclasses)
    record_dict_class = RecordDict

    # should be one of the three values: 'event', 'bl', 'hifreq'
    # (note: this is a *subset* of n6lib.const.EVENT_TYPE_ENUMS;
    # see also: the 'type' item of a n6lib.record_dict.RecordDict)
    event_type = 'event'

    # whether a parsed file that results in no events should raise an error
    # (see: get_output_bodies())
    allow_empty_results = False


    #
    # Auxiliary classes

    @dataclasses.dataclass
    class CsvRawRows:

        """A class of an iterable that can be used as a CSV reader's source."""

        raw: bytes

        def __iter__(self) -> io.StringIO:
            decoded = self.raw.decode('utf-8', 'surrogateescape')
            return csv_string_io(decoded)


    #
    # Script running

    @classmethod
    def run_script(cls):
        with logging_configured():
            init_kwargs = cls.get_script_init_kwargs()
            parser = cls(**init_kwargs)
            parser.run_handling()

    @classmethod
    def get_script_init_kwargs(cls):
        """
        A class method: get a dict of kwargs for instantiation in a script.

        The default implementation returns an empty dict.
        """
        return {}


    #
    # Instance initialization/configuration

    def preinit_hook(self):
        # called after instance creation, before __init__()
        # (see: LegacyQueuedBase.__new__())

        # some unit tests are over-zealous about patching super()
        from builtins import super

        if self.default_binding_key is not None:  # (not for an abstract class)
            assert 'input_queue' in vars(self)  # ensured by LegacyQueuedBase.__new__()
            self.input_queue['queue_name'] = self.default_binding_key
        super().preinit_hook()

    @attr_required('default_binding_key')
    def __init__(self, **kwargs):
        assert self.event_type in ('event', 'bl', 'hifreq')
        super().__init__(**kwargs)
        self.set_configuration()
        # Note that the `prefetch_count` attribute (originally set as
        # a `LegacyQueuedBase`'s class attribute) is overridden here --
        # with the value from the parser-specific config.
        self.prefetch_count = self.config['prefetch_count']

    # * Configurable-pipeline-related hooks:

    def configure_pipeline(self):
        """
        The default binding keys, set in `default_binding_key`
        attribute, may be overridden in the pipeline configuration.
        """
        self.input_queue['binding_keys'] = [self.default_binding_key]
        super().configure_pipeline()

    def get_component_group_and_id(self):
        return 'parsers', self.__class__.__name__.lower()

    def make_binding_keys(self, binding_keys, *args, **kwargs):
        """
        If the `default_binding_key` attribute is not set in parser's
        subclass, try to obtain binding keys from the pipeline config.

        Args/kwargs:
            `binding_keys`:
                The list of new binding keys.
            <any other arguments>:
                Ignored.
        """
        self.input_queue['binding_keys'] = binding_keys

    # * AMQP-config-related hook (invoked in `LegacyQueuedBase.__init__()`):

    @classmethod
    def get_connection_params_dict(cls):
        params_dict = super().get_connection_params_dict()
        config_spec = as_config_spec_string(
            cls._aux_rabbitmq_config_spec_pattern,
            {'rabbitmq_config_section': cls.rabbitmq_config_section})
        config = Config.section(config_spec)
        params_dict['heartbeat_interval'] = config['heartbeat_interval_parsers']
        return params_dict

    _aux_rabbitmq_config_spec_pattern = '''
        [{rabbitmq_config_section}]
        heartbeat_interval_parsers :: int
        ...
    '''

    # * Parser-specific-config-related hooks:

    def set_configuration(self) -> None:
        """
        Set the configuration-related attributes.

        This method is called in `BaseParser`'s `__init__()`.
        """
        format_kwargs = self.get_config_spec_format_kwargs()
        parser_class_name = format_kwargs['parser_class_name']
        assert parser_class_name == self.__class__.__name__
        self.config_full = self.get_config_full(**format_kwargs)
        self.config = self.config_full[parser_class_name]

    def get_config_spec_format_kwargs(self) -> KwargsDict:
        """
        A hook invoked by `set_configuration()`: get the *format data
        dict* -- to be used to format the actual *config spec* (based on
        the value of the `config_spec_pattern` attribute).

        The default implementation of this method returns a dictionary
        that contains just one key: `'parser_class_name'` -- the value
        is `__name__` of the parser class.

        This method will need to be extended (typically, using `super()`)
        in your subclasses if their `config_spec_pattern`s contain also
        other replacement fields (apart from `{parser_class_name}`).
        """
        return {'parser_class_name': self.__class__.__name__}


    #
    # Main activity

    def run_handling(self) -> None:
        """
        The main activity of the parser.

        The default implementation of this method -- which should be
        sufficient in nearly all cases -- performs the following
        actions:

        * (1) invoke the parser's `run()` method (which, in its default
          version implemented in `LegacyQueuedBase`, starts the `pika`'s
          event loop, that will be running until it finishes normally,
          or *Ctrl+C* is pressed, or some error occurs).

        * (2-a) If `run()` raised a `KeyboardInterrupt` exception
          (typically, because *Ctrl+C* was pressed), invoke the
          parser's `stop()` method (which, in its default version
          implemented in `LegacyQueuedBase`, stops the `pika`'s event
          loop), then re-raise the exception.

        * (2-b) If `run()` raised any other exception, just propagate
          it (without invoking `stop()`).

        * (2-c) If no exception occurred, just finish (note that, in
          this case, `stop()` should not be invoked because the `run()`
          method has finished its activity normally).
        """
        try:
            self.run()
        except KeyboardInterrupt:
            self.stop()
            raise


    #
    # Input data processing -- preparing output data

    def input_callback(self,
                       routing_key: str,
                       body: bytes,
                       properties: pika.BasicProperties) -> None:
        """
        A callback, typically called in LegacyQueuedBase.on_message().

        Args/kwargs:
            `routing_key`:
                The routing key used to publish the AMQP message.
            `body`:
                The AMQP message body.
            `properties`:
                A pika.BasicProperties instance containing properties of
                the AMQP message.

        This method calls the following parser-specific methods:

        * prepare_data(),
        * get_output_rk(),
        * get_output_bodies(),
        * and for each item of the sequence returned by get_output_bodies():
          * publish_output() (this one is defined in a superclass --
            typically it is LegacyQueuedBase.publish_output()).

        Default implementations of these methods should be sensible in
        most cases.
        """
        data = self.prepare_data(routing_key, body, properties)
        rid = data.get('properties.message_id')
        with self.setting_error_event_info(rid):
            output_rk = self.get_output_rk(data)
            with FilePagedSequence(page_size=1000) as working_seq:
                for output_body in self.get_output_bodies(data, working_seq):
                    self.publish_output(routing_key=output_rk, body=output_body)

    def prepare_data(self, routing_key, body, properties):
        """
        Extract basic input data from message, its routing key and properties.

        Args/kwargs:
            `routing_key` (string):
                The routing key used to publish the AMQP message.
            `body` (bytes):
                The AMQP message body.
            `properties` (pika.BasicProperties instance):
                Properties of the AMQP message.

        Returns:
            A dictionary containing the extracted data which are:

            * attributes of the `headers` attribute of `properties`;
            * other attributes of `properties` -- each with its key
              prefixed with 'properties.';
            * the 'source' item which is the *source specification*
              string, aka *source id*, aka *source* (in the format:
              `<source provider>.<source channel>`) extracted from
              `routing_key`;
            * the 'raw_format_version_tag' item which is None or a
              string being a tag denoting the version of the raw data
              format (aka *raw format version tag*), in the format:
              `<4-digit year><2-digit month>`, extracted from
              `routing_key`;
            * the 'raw' item which is simply `body`;
            * the 'csv_raw_rows' item which is an iterable (lazily
              initialized) that yields str objects being raw CSV rows
              of `body`, decoded using the "utf-8" codec with the
              "surrogateescape" error handler (which means that each
              of non-UTF-8 bytes -- if any -- is replaced with the
              corresponding surrogate codepoint); the iterable is ready
              to be used as the input file/iterable argument to a
              csv.reader or csv.DictReader.

        Typically, this method is used indirectly -- being called in
        input_callback().
        """
        assert isinstance(body, bytes)

        # custom AMQP headers (if any)
        data = (properties.headers.copy() if properties.headers is not None
                else {})

        # basic AMQP properties -- each key prefixed with 'properties.'
        properties.timestamp = str(datetime.utcfromtimestamp(properties.timestamp))
        data.update(('properties.' + key, value)
                    for key, value in vars(properties).items()
                    if key != 'headers')

        # the *source specification* string (aka *source id*, aka *source*)
        # and the *raw format version tag*
        source_provider, rest_of_rk = routing_key.split('.', 1)
        source_channel, _, raw_format_version_tag = rest_of_rk.partition('.')
        data['source'] = f'{source_provider}.{source_channel}'
        data['raw_format_version_tag'] = (
            raw_format_version_tag if raw_format_version_tag
            else None)

        data['raw'] = body
        data['csv_raw_rows'] = self.CsvRawRows(raw=body)

        return data

    def get_output_rk(self, data):
        """
        Get the output routing key.

        Args/kwargs:
            `data` (dict):
                As returned by prepare_data() (especially, its 'source' item
                contains the *source specification* string, aka *source id*, aka
                *source* -- in the format: `<source provider>.<source channel>`).

        Returns:
            A string being the output routing key.

        Typically, this method is used indirectly -- being called in
        input_callback().
        """
        return '{}.parsed.{}'.format(self.event_type, data['source'])

    def get_output_bodies(self, data, working_seq):
        """
        Process given data and make a list of serialized events.

        Args/kwargs:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw input data body).
            `working_seq` (a sequence...):
                An empty list-like sequence to be used for processing.
                It must support at least the following operations:
                .append, .__setitem__, iter, len (and bool).

        Yields:
            The sequence passed in as the `working_seq` argument -- filled
            with bytes instances, each being JSON-serialized event data dict.

        This method calls the following parser-specific methods:

        * parse() (must be implemented in concrete subclasses!),
        * get_output_message_id(),
        * postprocess_parsed().

        It also does some operations on record dicts yielded by parse()
        and returned by postprocess_parsed(), especially:

        * setting the 'id' item.
        * getting a ready JSON string (containing serialized event data).

        Typically, this method is used indirectly -- being called in
        input_callback().
        """
        for parsed in self.parse(data):
            assert isinstance(parsed, RecordDict)
            if not parsed.used_as_context_manager:
                raise AssertionError('record dict yielded in a parser must be '
                                     'treated with a "with ..." statement!')
            parsed["id"] = self.get_output_message_id(parsed)
            self.delete_too_long_address(parsed)
            working_seq.append(parsed)
        total = len(working_seq)
        for i, parsed in enumerate(working_seq):
            with self.setting_error_event_info(parsed):
                parsed = self.postprocess_parsed(data, parsed, total,
                                                 item_no=(i + 1))
                working_seq[i] = parsed.get_ready_json().encode('utf-8')
        if not working_seq and not self.allow_empty_results:
            raise ValueError('no output data to publish; either all data '
                             'items caused AdjusterError (you can look '
                             'for apropriate warnings in logs) or input '
                             'data contained no actual data items')
        # we have parsed and postprocessed all data so now
        # we can start publishing without fear of breaking
        # publishing in the midst by a data error
        return working_seq

    def delete_too_long_address(self, parsed):
        # XXX: shouldn't this behavior be changed to some less destructive one? See #8525...
        _address = parsed.get('address')
        if _address and len(_address) > MAX_IPS_IN_ADDRESS:
            del parsed['address']
            LOGGER.warning('Too many IPs in `address`: %s (event id: %a), '
                           'so the `address` attribute has been deleted',
                           len(_address), parsed['id'])

    ## NOTE: typically, this method must be implemented in concrete subclasses
    def parse(self, data):
        """
        Parse the data, generating parsed data record dicts.

        Args/kwargs:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw input data body).

        Yields:
            RecordDict instances containing parsed data which, after adding
            the 'id' item and serializing, would be ready to be published.

        Typically, this method is used indirectly -- being called in
        get_output_bodies().

        Note #1: In BaseParser, this is a method placeholder (aka abstract
        method); you *need* to implement this method in your subclass as a
        generator function (or something else that returns a generator or
        another kind of iterator). RecordDict instance(s) produced by it
        should be created, treated and yielded in the following way:

            with self.new_record_dict(data) as parsed:
                ...
                # here: some operations -- adding items to `parsed`...
                ...
                yield parsed

        Thanks to that, if an error occurs within such a `with` block, it
        will be caught and automatically passed into the handle_parse_error()
        parser method which can decide whether the error is propagated or
        silenced (if the error is silenced the execution continues
        immediately following the `with` block).

        Note #2: In your implementation you do not need to set in the
        resultant record dict attributes that are automatically placed
        there by other parser methods.  That attributes are:

        * those placed in the record dict immediately after it is created
          by calling self.new_record_dict() (so in very rare cases you may
          want to overwrite some of them in your parse() implementation):

          * all items from <your parser>.constant_items,
          * 'rid',
          * 'source';

        * those placed in the record dict after it is yielded by parse()
          (so you cannot set them in parse() and you should never need
          to do so):

          * 'id',
          * some attributes concerning only specific subclasses, e.g.:
            * '_group' (AggregatedEventParser-specific),
            * '_bl-series-id', '_bl-series-total', '_bl-series-no'
              (BlackListParser-specific).

        Example implementation of parse():

            def parse(data):
                rows = csv.DictReader(data['csv_raw_rows']),
                                      fieldnames=['url', 'ip'],
                                      delimiter='|', quotechar='"')
                for row in rows:
                    with self.new_record_dict(data) as parsed:
                        parsed['time'] = data['properties.timestamp']
                        parsed['url'] = row['url']
                        parsed['address'] = {'ip': row['ip']}
                        yield parsed

        Another example:

            def parse(data):
                doc = json.loads(data['raw'])
                with self.new_record_dict(data) as parsed:
                    parsed['time'] = doc['ISODateTimeOfDetection']
                    parsed['fqdn'] = doc['FullyQualifiedDomainName']
                    yield parsed
        """
        raise NotImplementedError

    def new_record_dict(self, data, **record_dict_kwargs):
        """
        Make a new record dict instance.

        Args/kwargs:
            `data` (dict):
                As returned by prepare_data().

        Kwargs:
            Optional keyword arguments to be passed into the record dict
            factory (into the `record_dict_class` attribute of the parser
            class).

            Note that the `log_nonstandard_names` and
            `context_manager_error_callback` record dict factory
            arguments should not be specified as they are always
            passed in automatically.

        Returns:
            A new RecordDict instance, populated by calling set_basic_items()
            on it.

        This method is intended to be called in the parse() method to create
        new record dicts.
        """
        # TODO later: remove this transitional assertion + corresponding line in tests...
        assert not hasattr(self, 'record_dict_kwargs'), 'attribute not supported anymore'
        record_dict = self.record_dict_class(
            log_nonstandard_names=True,
            context_manager_error_callback=self.handle_parse_error,
            **record_dict_kwargs)
        self.set_basic_items(record_dict, data)
        return record_dict

    # TODO: check whether and which picklability-related requirements
    #       described in the docstring of the following method are still
    #       necessary.
    @staticmethod
    @picklable
    def handle_parse_error(context_manager_error):
        """
        Passed into record dict as the `context_manager_error_callback` arg.

        Args/kwargs:
            `context_manager_error` (an exception instance):
                An exception raised within a record-dict-managed
                `with` block in the parse() method (see its docs
                for details).

        Returns:
            True of False:

            * True means that the error will be silenced and execution
              of the parse() method will be continued from the point
              immediately after the `with` block;

            * False means that the error will be propagated (i.e.,
              execution of the parse() method will be broken).

        Important: the handle_parse_error() method must be picklable
        (otherwise record dicts will not be picklable) -- so:

        * it must be a function (not an instance method or class method);
          that's why it must be decorated with @staticmethod;

        * it must be possible to import this function using the values
          of its __module__ and __name__/__qualname__ attributes; the easiest
          way to ensure that it is possible is to decorate the function with
          the @n6lib.common_helpers.picklable decorator.

        The new_record_dict() method passes this function into the record
        dict constructor.  Then this function is called if and when an
        error occurs within the record dict's `with` block (see: parse()).

        It is recommended that this function, before returning True, first
        logs a warning.

        The default implementation of this function:

        * returns True (after logging a warning) if `context_manager_error`
          is an AdjusterError instance,

        * returns False otherwise.

        (But see the implementation in the BlackListParser class...).
        (See also: SkipParseExceptionsMixin).
        """
        if isinstance(context_manager_error, AdjusterError):
            LOGGER.warning('Event could not be generated due to %s',
                           make_exc_ascii_str(context_manager_error))
            return True
        else:
            return False

    def set_basic_items(self, record_dict, data):
        """
        Populate the given record dict with basic data items.

        Args/kwargs:
            `record_dict` (a RecordDict instance):
                The record dict to be populated.
            `data` (dict):
                As returned by prepare_data().

        Typically, this method is used indirectly -- being called
        in new_record_dict().

        This method makes use of the `constant_items` attribute.
        """
        if self.constant_items is not None:
            record_dict.update(self.constant_items)
        record_dict['rid'] = data['properties.message_id']
        record_dict['source'] = data['source']

    def get_output_message_id(self, parsed):
        """
        Make the id of the output message (aka `id`).

        Args/kwargs:
            `parsed` (a RecordDict instance):
                As yielded by parse().

        Returns:
            A string being the output message id.

        Typically, this method is used indirectly -- being called in
        get_output_bodies().
        """
        # Be careful when modifying this method or any method that this
        # method does call: after any code changes it should generate
        # the same ids for already stored data!  (That's why this code
        # may already seem weird a bit...)
        assert isinstance(parsed, RecordDict)
        components = []
        for k, v in sorted(self.iter_output_id_base_items(parsed)):
            if not isinstance(k, str):
                raise TypeError('encountered a non-str key ({!a})'
                                .format(k))
            k = as_bytes(k)
            if isinstance(v, (list, tuple)):
                v = b','.join(sorted(map(self._deterministic_conv_to_bytes, v)))
            else:
                v = self._deterministic_conv_to_bytes(v)
            assert isinstance(k, bytes)
            assert isinstance(v, bytes)
            components.append(b'%b,%b' % (k, v))
        hashed_bytes = b'\n'.join(components)
        return hashlib.md5(hashed_bytes, usedforsecurity=False).hexdigest()

    def _deterministic_conv_to_bytes(self, value):
        CONVERTIBLE_TO_BYTES_TYPES = str, bytes, bytearray, memoryview, SupportsBytes
        if isinstance(value, dict):
            converted_key_to_val = {}
            for k, v in value.items():
                if not isinstance(k, (str, bytes)):
                    raise TypeError('dict {!a} contains a non-str-or-bytes key ({!a})'
                                    .format(value, k))
                k = self._py2_bytestring_like_repr(k).encode('ascii')
                if isinstance(v, int):
                    v = b'%d' % v
                else:
                    if not isinstance(v, CONVERTIBLE_TO_BYTES_TYPES):
                        raise TypeError('dict {!a} contains a value ({!a}) '
                                        'whose type ({!a}) is illegal'
                                        .format(value, v, type(v)))
                    v = self._py2_bytestring_like_repr(v).encode('ascii')
                assert isinstance(k, bytes)
                assert isinstance(v, bytes)
                converted_key_to_val[k] = v
            value = b'{%b}' % b', '.join(b'%b: %b' % (k, v)
                                         for k, v in sorted(converted_key_to_val.items()))
        elif isinstance(value, int):
            value = b'%d' % value
        else:
            if not isinstance(value, CONVERTIBLE_TO_BYTES_TYPES):
                raise TypeError('encountered a value ({!a}) '
                                'whose type ({!a}) is illegal)'
                                .format(value, type(value)))
            value = as_bytes(value)
        assert isinstance(value, bytes)
        return value

    def _py2_bytestring_like_repr(self, obj):
        ascii_repr = ascii(as_bytes(obj))
        assert ascii_repr.startswith(("b'", 'b"'))
        return ascii_repr[1:]

    def iter_output_id_base_items(self, parsed):
        """
        Generate items to become the base for the output message id.

        Args/kwargs:
            `parsed` (a RecordDict instance):
                As yielded by parse().

        Yields:
            2-element (key, value) tuples to become the base for
            the output message id.

        Typically, this method is used indirectly -- being called in
        get_output_message_id().

        Note #1: If overridden in a subclass -- it should either be a
        generator method or a method that returns a generator or other
        iterator.

        Note #2: The default implementation of this method yields all
        items of `parsed` except those whose keys start with '_'.
        You may want to extend this method in your subclass --
        e.g. to filter out some items.
        """
        return ((k, v) if k != 'name' else (k, parsed._get_name_in_legacy_form())
                for k, v in parsed.items()
                if not k.startswith('_'))  # no internal flag keys

    def postprocess_parsed(self, data, parsed, total, item_no):
        """
        Postprocess parsed data.

        Args/kwargs:
            `data` (dict):
                As returned by prepare_data().
            `parsed` (RecordDict instance):
                The parsed event data (a RecordDict instance).
            `total` (int):
                Total number of parsed events (within latest parse() call).
            `item_no` (int):
                The number of this parsed event (within latest parse() call).

        Returns:
            A RecordDict instance.

        The basic implementation of this method sets
        '_do_not_resolve_fqdn_to_ip' in `parsed` if needed.

        The method can be extended in subclasses if additional processing
        of parsed data is needed -- for example, see: BlackListParser).

        Typically, this method is used indirectly -- being called in
        get_output_bodies(), just before serializing the record dict
        into a JSON string.
        """
        if do_not_resolve_fqdn_to_ip := data.get('_do_not_resolve_fqdn_to_ip'):
            assert do_not_resolve_fqdn_to_ip is True
            parsed['_do_not_resolve_fqdn_to_ip'] = True
        return parsed


    #
    # Some helpers to be used in parser implementations

    @staticmethod
    def set_proto(parsed, proto_symbol_number,
                  _symbol_number_to_proto={'1': 'icmp',
                                           '6': 'tcp',
                                           '17': 'udp'}):
        proto_symbol_number = str(proto_symbol_number)
        try:
            parsed['proto'] = _symbol_number_to_proto[proto_symbol_number]
        except KeyError:
            LOGGER.warning('Unrecognized proto symbol number: %a',
                           proto_symbol_number)


class SkipParseExceptionsMixin(object):

    """
    A mixin that provides such an implementation of handle_parse_error()
    that skips any Exception instances, not only AdjusterError instances
    (see BaseParser.handle_parse_error()...).

    Note: exceptions such as SystemExit or KeyboardInterrupt, i.e.,
    *not* being instances of Exception (direct or indirect), will
    *not* be skipped.
    """

    @staticmethod
    @picklable
    def handle_parse_error(context_manager_error):
        if isinstance(context_manager_error, Exception):
            LOGGER.warning('Event could not be generated due to %s',
                           make_exc_ascii_str(context_manager_error))
            return True
        return False


class AggregatedEventParser(BaseParser):

    """
    The main base class for aggregated-event-parsers.
    """

    event_type = 'hifreq'

    # in concrete subclasses `group_id_components` *must*
    # be set to an event attribute name or a sequence of
    # event attribute names; values of the attributes will
    # be used to form the '_group' attribute value;
    # two additional notes:
    # * special case: 'ip' -- means: address[0].get('ip');
    # * for non-existent items the 'None' string will be
    #   used as the value, however at least one attribute
    #   must be present (and not None) or ValueError will
    #   be raised
    group_id_components = None

    @attr_required('group_id_components')
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def postprocess_parsed(self, data, parsed, total, item_no):
        parsed = super().postprocess_parsed(data, parsed, total, item_no)
        group_id_components = ([self.group_id_components]
                               if isinstance(self.group_id_components, str)
                               else self.group_id_components)
        component_values = [self._get_component_value(parsed, name)
                            for name in group_id_components]
        if all(v is None
               for v in component_values):
            raise ValueError('none of the group id components ({}) '
                             'is set to a non-None value (in {!a})'
                             .format(', '.join(group_id_components),
                                     parsed))
        parsed['_group'] = '_'.join(map(ascii_str, component_values))
        return parsed

    @staticmethod
    def _get_component_value(mapping, name):
        if name == 'ip':
            try:
                return mapping['address'][0]['ip']
            except (KeyError, IndexError):
                return None
        return mapping.get(name)


class BlackListParser(BaseParser):

    """
    The main base class for black-list-parsers.
    """

    record_dict_class = BLRecordDict
    event_type = 'bl'

    # name of the regex capturing group with a matched datetime
    bl_current_time_regex_group = 'datetime'

    # If set in a subclass, the parser will use it to extract
    # `_bl-current-time` attribute's value from a data fetched
    # by a collector. The matched datetime should be inside
    # a capturing group identified by the name set in the
    # `bl_current_time_regex_group` class attribute.
    bl_current_time_regex = None

    # If set in a subclass, a date+time, as a string, extracted
    # using `bl_current_time_regex`, will be converted with
    # a `datetime.datetime.strptime()` using this format. Does not
    # have to be set, if the datetime is in the ISO format.
    bl_current_time_format = None

    @staticmethod
    @picklable
    def handle_parse_error(context_manager_error):
        # any error breaks whole parse() call without publishing anything
        return False

    def postprocess_parsed(self, data, parsed, total, item_no):
        parsed = super().postprocess_parsed(data, parsed, total, item_no)
        parsed.update({
            "_bl-series-id": data["properties.message_id"],
            "_bl-series-total": total,
            "_bl-series-no": item_no,
            "_bl-time": data['properties.timestamp'],
            "_bl-current-time": self._get_bl_current_time(data, parsed)
        })
        return parsed

    def _get_bl_current_time(self, data, parsed):
        bl_current_time = self.get_bl_current_time_from_data(data, parsed)
        if bl_current_time:
            return bl_current_time
        # if _bl-current-time value cannot be extracted from data,
        # get it from AMQP headers
        if 'meta' in data:
            mail_time = data['meta'].get('mail_time')
            if mail_time:
                return mail_time
            http_last_modified = data['meta'].get('http_last_modified')
            if http_last_modified:
                return http_last_modified
        return data['properties.timestamp']

    def get_bl_current_time_from_data(self, data, parsed):
        if self.bl_current_time_regex:
            raw_as_str = data['raw'].decode('utf-8', 'surrogateescape')
            match = self.bl_current_time_regex.search(raw_as_str)
            if match:
                bl_current_time = match.group(self.bl_current_time_regex_group)
                if bl_current_time:
                    if self.bl_current_time_format:
                        return datetime.strptime(bl_current_time,
                                                 self.bl_current_time_format)
                    return parse_iso_datetime_to_utc(bl_current_time)
        return None


#
# Entry point factory

def add_parser_entry_point_functions(module):
    if isinstance(module, str):
        module = sys.modules[module]
    for name in dir(module):
        if not name.startswith('_'):
            obj = getattr(module, name)
            is_parser_class = isinstance(obj, type) and issubclass(obj, BaseParser)
            if is_parser_class:
                assert hasattr(obj, 'run_script')
                setattr(module, f'{name}_main', obj.run_script)

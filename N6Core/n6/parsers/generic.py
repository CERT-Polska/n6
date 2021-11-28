# -*- coding: utf-8 -*-

# Copyright (c) 2013-2021 NASK. All rights reserved.

"""
Parser base classes + auxiliary tools.
"""

import hashlib
import itertools
import operator
from cStringIO import StringIO
from datetime import datetime

from lxml import etree

from n6.base.queue import QueuedBase
from n6lib.class_helpers import all_subclasses, attr_required
from n6lib.common_helpers import (
    FilePagedSequence,
    ascii_str,
    make_exc_ascii_str,
    picklable,
)
from n6lib.config import Config, ConfigMixin
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger, logging_configured
from n6lib.record_dict import (
    AdjusterError,
    RecordDict,
    BLRecordDict,
)


LOGGER = get_logger(__name__)

MAX_IPS_IN_ADDRESS = 63


# TODO: finish tests
class BaseParser(ConfigMixin, QueuedBase):

    """
    The "root" base class for parsers.
    """

    # these attributes are default base for actual instance attributes
    # `input_queue` and `output_queue` (see QueuedBase.__new__()
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

    # a string
    #    '<source label>.<source channel>'
    # or '<source label>.<source channel>.<raw format version tag>'
    # that typically is used as:
    # * the name of the input queue
    # * the binding key for the input queue
    # (it *should* be set in subclasses -- as the standard implementations
    # of the preinit_hook() and make_binding_keys() methods make use of it)
    default_binding_key = None

    # a dict of default items for each resultant record dict
    # (it can be left as None)
    constant_items = None

    # the default config spec pattern for parsers; it can be
    # overridden in subclasses provided that the new value will
    # specify the `[{parser_class_name}]` section including the
    # `prefetch_count` option with the `int` converter [hint:
    # the attribute can be easily extended using the
    # n6lib.config.join_config_specs() helper]
    config_spec_pattern = '''
        [{parser_class_name}]
        prefetch_count = 1 :: int
    '''

    # a record dict class -- n6lib.record_dict.RecordDict or its subclass
    # (can be overridden in subclasses)
    record_dict_class = RecordDict

    # standard keyword arguments to be passed into the record
    # dict constructor defined above (in subclasses it can be
    # left as None or overridden)
    record_dict_kwargs = None

    # should be one of the three values: 'event', 'bl', 'hifreq'
    # (note: this is a *subset* of n6lib.const.TYPE_ENUMS;
    # see also: n6lib.record_dict.RecordDict's 'type' key)
    event_type = 'event'

    # whether a parsed file that results in no events should raise an error
    # (see: get_output_bodies())
    allow_empty_results = False


    @attr_required('default_binding_key')
    def __init__(self, **kwargs):
        assert self.event_type in ('event', 'bl', 'hifreq')
        super(BaseParser, self).__init__(**kwargs)
        self.set_configuration()
        # the attribute is overridden in order to supply each parser
        # with an adjusted value of the prefetch count from its
        # config
        self.prefetch_count = self.config['prefetch_count']

    def set_configuration(self):
        """Set the configuration-related attributes."""
        parser_class_name = self.__class__.__name__
        config_full = self.get_config_full(parser_class_name=parser_class_name)
        # `config` -- contains the options from
        # the {parser_class_name} config section
        self.config = config_full[parser_class_name]
        # `config_full` -- will be useful when you declare more
        # config sections in `config_spec_pattern` of a subclass
        self.config_full = config_full


    #
    # Other pre-init-related methods

    @classmethod
    def get_script_init_kwargs(cls):
        """
        A class method: get a dict of kwargs for instantiation in a script.

        The default implementation returns an empty dict.
        """
        return {}

    def preinit_hook(self):
        # called after instance creation, before __init__()
        # (see: n6.base.queue.QueuedBase.__new__())

        # some unit tests are over-zealous about patching super()
        from __builtin__ import super

        if self.default_binding_key is not None:  # (not for an abstract class)
            assert 'input_queue' in vars(self)  # ensured by QueuedBase.__new__()
            self.input_queue['queue_name'] = self.default_binding_key
        super(BaseParser, self).preinit_hook()

    def configure_pipeline(self):
        """
        The default binding keys, set in `default_binding_key`
        attribute, may be overridden in the pipeline configuration.
        """
        self.input_queue['binding_keys'] = [self.default_binding_key]
        super(BaseParser, self).configure_pipeline()

    def get_component_group_and_id(self):
        return 'parsers', self.__class__.__name__.lower()

    def make_binding_keys(self, binding_keys, *args, **kwargs):
        """
        If the `default_binding_key` attribute is not set in parser's
        subclass, try to obtain binding keys from the pipeline config.

        Args:
            `binding_keys`:
                The list of new binding keys.
        """
        self.input_queue['binding_keys'] = binding_keys

    #
    # Utility static method extensions

    @classmethod
    def get_connection_params_dict(cls):
        params_dict = super(BaseParser, cls).get_connection_params_dict()
        config = Config(required={cls.rabbitmq_config_section: ("heartbeat_interval_parsers",)})
        queue_conf = config[cls.rabbitmq_config_section]
        params_dict['heartbeat_interval'] = int(queue_conf['heartbeat_interval_parsers'])
        return params_dict


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
    ### (or maybe somewhere in main...)
    ### (+ also for all other components?)


    #
    # Input data processing -- preparing output data

    def input_callback(self, routing_key, body, properties):
        """
        A callback, typically called in QueuedBase.on_message().

        Args:
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
            typically it is QueuedBase.publish_output()).

        Default implementations of these methods should be sensible in
        most cases.
        """
        body = self._fix_body(body)
        data = self.prepare_data(routing_key, body, properties)
        rid = data.get('properties.message_id')
        with self.setting_error_event_info(rid):
            output_rk = self.get_output_rk(data)
            with FilePagedSequence(page_size=1000) as working_seq:
                for output_body in self.get_output_bodies(data, working_seq):
                    self.publish_output(routing_key=output_rk, body=output_body)

    @staticmethod
    def _fix_body(body):
        # pika < 0.9.14 seems to pass in `body` as unicode when data are
        # utf-8-decodable and we want it to be consistent: always str
        return (body.encode('utf-8') if isinstance(body, unicode)
                else body)

    def prepare_data(self, routing_key, body, properties):
        """
        Extract basic input data from message, its routing key and properties.

        Args:
            `routing_key` (string):
                The routing key used to publish the AMQP message.
            `body` (string):
                The AMQP message body.
            `properties` (pika.BasicProperties instance):
                Properties of the AMQP message.

        Returns:
            A dictionary containing the extracted data which are:
            * attributes of the `headers` attribute of `properties`;
            * other attributes of `properties` -- each with its key
              prefixed with 'properties.';
            * the 'source' item which is the source specification string
              extracted from `routing_key`;
            * the 'raw_format_version_tag' item which is None or a string
              being the tag of the raw data format version;
            * the 'raw' item which is simply `body`.

        Typically, this method is used indirectly -- being called in
        input_callback().
        """
        # custom AMQP headers (if any)
        data = (properties.headers.copy() if properties.headers is not None
                else {})

        # basic AMQP properties -- each key prefixed with 'properties.'
        properties.timestamp = str(datetime.utcfromtimestamp(properties.timestamp))
        data.update(('properties.' + key, value)
                    for key, value in vars(properties).iteritems()
                    if key != 'headers')

        # the source specification string and the format version tag
        source_label, rest_of_rk = routing_key.split('.', 1)
        source_channel, _, raw_format_version_tag = rest_of_rk.partition('.')
        data['source'] = '{}.{}'.format(source_label, source_channel)
        data['raw_format_version_tag'] = (
            raw_format_version_tag if raw_format_version_tag
            else None)

        # the raw data body
        data['raw'] = body
        return data

    def get_output_rk(self, data):
        """
        Get the output routing key.

        Args:
            `routing_key` (string):
                The routing key used to publish the AMQP message.
            `data` (dict):
                As returned by prepare_data() (especially, its 'source' item
                contains the source specification string).

        Returns:
            A string being the output routing key.

        Typically, this method is used indirectly -- being called in
        input_callback().
        """
        return '{}.parsed.{}'.format(self.event_type, data['source'])

    def get_output_bodies(self, data, working_seq):
        """
        Process given data and make a list of serialized events.

        Args:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw data body).
            `working_seq` (a sequence...):
                An empty list-like sequence to be used for processing.
                It must support at least the following operations:
                .append, .__setitem__, iter, len (and bool).

        Yields:
            The sequence passed in as the `working_seq` argument -- filled
            with strings, each being JSON-serialized event data dict.

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
                working_seq[i] = parsed.get_ready_json()
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
        _address = parsed.get('address')
        if _address and len(_address) > MAX_IPS_IN_ADDRESS:
            del parsed['address']
            LOGGER.warning('To many IPs in `address`: %s (event id: %r), '
                           'so the `address` attribute has been deleted',
                           len(_address), parsed['id'])

    ## NOTE: typically, this method must be implemented in concrete subclasses
    def parse(self, data):
        """
        Parse the data, generating parsed data record dicts.

        Args:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw data body).

        Yields:
            RecordDict instances containing parsed data which, after adding
            the 'id' item and serializing, would be ready to be published.

        Typically, this method is used indirectly -- being called in
        get_output_bodies().

        Note #1: In BaseParser, this is a method placeholder (aka abstract
        method); you *need* to implement this method in your subclass as
        a generator (or something that returns generator or other iterator).
        The RecordDict instance(s) it yields *must* be created, treated and
        yielded in the following way:

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
          (so in very rare cases you may want to overwrite some of them
          in your parse() implementation):

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
                rows = csv.DictReader(cStringIO.StringIO(data['raw']),
                                      fieldnames=['url', 'ip'],
                                      delimiter='|', quotechar='"')
                for row in rows:
                    with self.new_record_dict(data) as parsed:
                        parsed['time'] = data['properties.timestamp']
                        parsed['url'] = row['url']
                        parsed['address'] = {'ip': row['ip']}
                        yield parsed
        """
        raise NotImplementedError

    def new_record_dict(self, data, **record_dict_kwargs):
        """
        Make a new record dict instance.

        Args:
            `data` (dict):
                As returned by prepare_data().

        Kwargs:
            Optional keyword arguments to be passed into the record dict
            factory (into the `record_dict_class` attribute of the parser
            class) together with the items from the `record_dict_kwargs`
            attribute of the parser class (in case of conflict the items
            given as arguments override those from the attribute).

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
        if self.record_dict_kwargs is not None:
            record_dict_kwargs = dict(self.record_dict_kwargs,
                                      **record_dict_kwargs)
        record_dict = self.record_dict_class(
            log_nonstandard_names=True,
            context_manager_error_callback=self.handle_parse_error,
            **record_dict_kwargs)
        self.set_basic_items(record_dict, data)
        return record_dict

    @staticmethod
    @picklable
    def handle_parse_error(context_manager_error):
        """
        Passed into record dict as the `context_manager_error_callback` arg.

        Args:
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
          of its __module__ and __name__ attributes; the easiest way to
          ensure that it is possible is to decorate the function with
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
            LOGGER.warning('Event could not be generated due to '
                           'AdjusterError: %s', context_manager_error)
            return True
        else:
            return False

    def set_basic_items(self, record_dict, data):
        """
        Populate the given record dict with basic data items.

        Args:
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
        Make the id of the output message.

        Args:
            `parsed` (dict):
                As yielded by parse().

        Returns:
            A string being the output message id.

        Typically, this method is used indirectly -- being called in
        get_output_bodies().
        """
        # Be careful when modifying this method or any method that this
        # method does call: after any code changes it should generate
        # the same ids for already stored data!  (That's why this code
        # may already seem to be weird a bit...)
        assert isinstance(parsed, RecordDict)
        serialized = []
        for k, v in sorted(self.iter_output_id_base_items(parsed)):
            if isinstance(v, (list, tuple)):
                v = ('{}'.format(self._prepare_for_deterministic_serialization(el))
                     for el in v)
                v = ','.join(sorted(v))
            v = self._prepare_for_deterministic_serialization(v)
            serialized.append("{},{}".format(k, v))
        return hashlib.md5("\n".join(serialized)).hexdigest()

    def _prepare_for_deterministic_serialization(self, value):
        VALUE_TYPES = str, int, long
        if isinstance(value, dict):
            item_reprs = {}
            for k, v in value.iteritems():
                if isinstance(k, unicode):
                    k = k.encode('utf-8')
                if isinstance(v, unicode):
                    v = v.encode('utf-8')
                if not isinstance(k, str):
                    raise TypeError('dict {!r} contains a non-string key ({!r})'
                                    .format(value, k))
                if not isinstance(v, VALUE_TYPES):
                    raise TypeError('dict {!r} contains a value ({!r}) '
                                    'whose type ({!r}) is illegal'
                                    .format(value, v, type(v)))
                # non-canonical, int-like repr for long (without the 'L' suffix)
                # -- because: whether a number is long is platform-dependant
                item_reprs[repr(k)] = (repr(v) if not isinstance(v, long)
                                       else str(v))
            value = '{%s}' % ', '.join('{}: {}'.format(k, v)
                                       for k, v in sorted(item_reprs.iteritems()))
            assert isinstance(value, str)
        elif isinstance(value, unicode):
            value = value.encode('utf-8')
        if not isinstance(value, VALUE_TYPES):
            raise TypeError('encountered a value ({!r}) '
                            'whose type ({!r}) is illegal)'
                            .format(value, type(value)))
        return value

    def iter_output_id_base_items(self, parsed):
        """
        Generate items to become the base for the output message id.

        Args:
            `parsed` (dict):
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
        items of `parsed` except those whose keys start with'_'.
        You may want to extend this method in your subclass --
        e.g. to filter out some items.
        """
        return ((k, v) for k, v in parsed.iteritems()
                if not k.startswith('_'))  # no internal flag keys

    def postprocess_parsed(self, data, parsed, total, item_no):
        """
        Postprocess parsed data.

        Args:
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
        if data.get('_do_not_resolve_fqdn_to_ip'):
            assert type(data.get('_do_not_resolve_fqdn_to_ip')) is bool
            parsed['_do_not_resolve_fqdn_to_ip'] = True
        return parsed


    #
    # Some helpers to be used in parser implementations

    @staticmethod
    def set_proto(parsed, proto_symbol_number,
                  _symbol_number_to_proto={'1': 'icmp',
                                           '6': 'tcp',
                                           '17': 'udp'}):
        try:
            parsed['proto'] = _symbol_number_to_proto[proto_symbol_number]
        except KeyError:
            LOGGER.warning('Unrecognized proto symbol number: %r',
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
        super(AggregatedEventParser, self).__init__(**kwargs)

    def postprocess_parsed(self, data, parsed, total, item_no):
        parsed = super(AggregatedEventParser,
                       self).postprocess_parsed(data, parsed, total, item_no)
        group_id_components = ([self.group_id_components]
                               if isinstance(self.group_id_components, basestring)
                               else self.group_id_components)
        component_values = [self._get_component_value(parsed, name)
                            for name in group_id_components]
        if all(v is None
               for v in component_values):
            raise ValueError('None of the group id components ({})'
                             'is set to a non-None value (in {!r})'
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
    # If set in a subclass, a datetime, as a string, extracted
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
        parsed = super(BlackListParser,
                       self).postprocess_parsed(data, parsed, total, item_no)
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
            match = self.bl_current_time_regex.search(data['raw'])
            if match:
                bl_current_time = match.group(self.bl_current_time_regex_group)
                if bl_current_time:
                    if self.bl_current_time_format:
                        return datetime.strptime(bl_current_time,
                                                 self.bl_current_time_format)
                    return parse_iso_datetime_to_utc(bl_current_time)
        return None



# LEGACY STUFF -- we DO NOT want to migrate it to `n6datasources.parsers.base`.
# IF it is really needed in Py3, please (TODO?) migrate it to
# `n6datasources.parsers.base_legacy`.
class TabDataParser(BaseParser):

    """
    The main base class for somewhat-typically-tabular-data-parsers.

    (Mainly for those that mimic old n6 perl scripts...)
    """

    # NOTE: parsing could be implemented using Python standard library
    # CSV tools but here *it is not* -- as it was easier (and in a way
    # more safe) to mimic Perl scripts which many parsers that inherit
    # from this class were based on...

    # this attribute *must* be set in concrete subclasses as a string
    # or None, where None means: any ASCII whitespace characters
    field_sep = NotImplemented

    # the following defaults *can* be overridden in concrete subclasses
    required_row_prefixes = None   # None or a string, or a tuple of strings
    ignored_row_prefixes = None    # None or a string, or a tuple of strings
    disable_row_rstrip = False
    disable_field_strip = False
    skip_first_row = False
    skip_blank_rows = False


    # auxiliary exception (to be used in process_row_fields() implementations)
    class SkipThisRow(Exception):
        """Raise this in process_row_fields() to skip the processed row."""


    @attr_required('field_sep', dummy_placeholder=NotImplemented)
    def __init__(self, **kwargs):
        super(TabDataParser, self).__init__(**kwargs)

    # for TabDataParser subclasses, *typically*, you
    # *DO NOT* need to re-implement/extend this method
    # -- implement process_row_fields() instead (see below...)
    def parse(self, data):
        SkipThisRow = self.SkipThisRow
        for row in self.iter_rows(data):
            with self.new_record_dict(data) as parsed:
                fields = self.get_row_fields(row)
                try:
                    r = self.process_row_fields(data, parsed, *fields)
                except SkipThisRow:
                    pass
                else:
                    # for absent-minded devs who return the SkipThisRow
                    # class or its instance instead of raising it :)
                    if r is not SkipThisRow and not isinstance(r, SkipThisRow):
                        yield parsed

    def get_row_fields(self, row):
        """
        Get a list of fields extracted from the given row.

        Args:
            `row` (str):
                As yielded by iter_rows().

        Returns:
            A list of this row's fields (each being an str).

        The default implementation of this method does the right thing
        for most cases.

        Typically, this method is used indirectly -- being called in parse().
        """
        fields = row.split(self.field_sep)
        if not self.disable_field_strip:
            fields = map(str.strip, fields)
        return fields

    def iter_rows(self, data):
        """
        Get an iterator over rows extracted from the raw data body.

        Args:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw data body).

        Returns:
            An iterator over data rows (each being an str).

        The default implementation of this method does the right thing
        for most cases.

        Typically, this method is used indirectly -- being called in parse().
        """
        raw_rows = StringIO(data['raw'])
        if self.skip_first_row:
            next(raw_rows)
        if not self.disable_row_rstrip:
            raw_rows = itertools.imap(str.rstrip, raw_rows)
            if self.skip_blank_rows:
                raw_rows = itertools.ifilter(None, raw_rows)
        else:
            raw_rows = itertools.imap(  # remove newline characters
                  operator.methodcaller('rstrip', '\r\n'),
                  raw_rows)
            if self.skip_blank_rows:
                raw_rows = itertools.ifilter(str.rstrip, raw_rows)
        if self.required_row_prefixes is not None:
            raw_rows = itertools.ifilter(
                  operator.methodcaller('startswith',
                                        self.required_row_prefixes),
                  raw_rows)
        if self.ignored_row_prefixes is not None:
            raw_rows = itertools.ifilterfalse(
                  operator.methodcaller('startswith',
                                        self.ignored_row_prefixes),
                  raw_rows)
        return raw_rows

    ## NOTE: typically, this method must be implemented in concrete subclasses
    def process_row_fields(self, data, parsed, *fields):
        """
        Process fields extracted from a row.

        Args:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw data body).
            `parsed` (a RecordDict instance):
                A record dict into which the method should put some data.
            Parser-specific positional arguments (each being an str):
                Fields extracted from the currently processed row.

        Returns:
            Normally the method call result is ignored -- except it is
            the TabDataParser.SkipThisRow class (or its instance) which
            indicates the same what raising TabDataParser.SkipThisRow
            does (see below). [It's a defensive programming technique
            against any absent-minded devs who return the SkipThisRow
            exception instead of raising it :)]

        Raises:
            TabDataParser.SkipThisRow to indicate that the processed
            row should be skipped (parse() will ommit yield for this
            row).

        This method need to be implemented in concrete subclasses.

        Typically, this method is used indirectly -- being called in parse().
        """
        raise NotImplementedError



# LEGACY STUFF -- we DO NOT want to migrate it to `n6datasources.parsers.base`.
# IF it is really needed in Py3, please (TODO?) migrate it to
# `n6datasources.parsers.base_legacy`.
class BlackListTabDataParser(TabDataParser, BlackListParser):

    """
    A variant od TabDataParser for black-list-parsers.
    """



# TODO: better docstrings and maybe some refactoring
#       (+ adding process_row_fields() method placeholder)
#       -- then update the wiki page about parsers...
# XXX: is it tested?
#
# LEGACY STUFF -- we DO NOT want to migrate it to `n6datasources.parsers.base`.
# IF it is really needed in Py3, please (TODO?) migrate it to
# `n6datasources.parsers.base_legacy`.
class XmlDataParser(BaseParser):

    """
    The main base class for somewhat-typically-xml-data-parsers.
    """

    # auxiliary exception (to be used in process_row_fields() implementations)
    class SkipThisRow(Exception):
        """Raise this in process_row_fields() to skip the processed row."""

    def parse(self, data):
        SkipThisRow = self.SkipThisRow
        for row in self.iter_entry(data):
            with self.new_record_dict(data) as parsed:
                try:
                    r = self.process_row_fields(data, parsed, row)
                except SkipThisRow as exc:
                    LOGGER.warning('SkipThisRow: %r', exc)
                else:
                    if isinstance(r, list):
                        for ins_rd in r:
                            yield ins_rd
                    else:
                        if r is not SkipThisRow and not isinstance(r, SkipThisRow):
                            yield parsed

    def iter_entry(self, data):
        """
        Get an iterator over rows extracted from the raw data body.

        Args:
            `data` (dict):
                As returned by prepare_data() (especially, its 'raw' item
                contains the raw data body).

        Returns:
            An iterator over xml tree:
        """
        raw_entry = StringIO(data['raw']).getvalue()
        parser = etree.XMLParser(ns_clean=True, remove_blank_text=True)
        tree = etree.fromstring(str(raw_entry), parser)
        return tree



#
# Script/entry point factories

# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
# (replaced by `n6datasources.parsers.base.BaseParser.run_script()`)
def generate_parser_main(parser_class):
    def parser_main():
        with logging_configured():
            init_kwargs = parser_class.get_script_init_kwargs()
            parser = parser_class(**init_kwargs)
            parser.run_handling()
    return parser_main


# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
# (use `n6datasources.parsers.base.add_parser_entry_point_functions()` instead)
def entry_point_factory(module):
    for parser_class in all_subclasses(BaseParser):
        if (not parser_class.__module__.endswith('.generic') and
              not parser_class.__name__.startswith('_')):
            setattr(module, "%s_main" % parser_class.__name__,
                    generate_parser_main(parser_class))

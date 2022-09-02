# -*- coding: utf-8 -*-

# Copyright (c) 2013-2022 NASK. All rights reserved.

"""
Collector base classes + auxiliary tools.
"""

import cPickle
import datetime
import hashlib
import json
import os
import sys
import time
import urllib
import urllib2
from math import trunc

import lxml.etree
import lxml.html

from n6lib.config import (
    ConfigError,
    ConfigMixin,
    ConfigSection,
)
from n6.base.queue import QueuedBase
from n6lib.class_helpers import (
    all_subclasses,
    attr_required,
)
from n6lib.common_helpers import (
    AtomicallySavedFile,
    make_exc_ascii_str,
)
from n6corelib.email_message import ReceivedEmailMessage

from n6lib.const import RAW_TYPE_ENUMS
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import (
    get_logger,
    logging_configured,
)



LOGGER = get_logger(__name__)



#
# Exceptions

# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
class n6CollectorException(Exception):
    pass



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


# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
class CollectorStateMixIn(object):

    """DO NOT USE THIS CLASS IN NEW CODE, USE ONLY CollectorWithStateMixin!"""

    _last_state = None
    _current_state = None

    def __init__(self, **kwargs):
        super(CollectorStateMixIn, self).__init__(**kwargs)


    def _get_last_state(self):
        self.cache_file_path = os.path.join(os.path.expanduser(self.config['cache_dir']),
                                            self.get_cache_file_name())
        try:
            with open(self.cache_file_path) as f:
                self._last_state = str(f.read().strip())
        except (IOError, ValueError):
            self._last_state = None
        LOGGER.info("Loaded last state '%s' from cache", self._last_state)

    def _save_last_state(self):
        self.cache_file_path = os.path.join(os.path.expanduser(self.config['cache_dir']),
                                            self.get_cache_file_name())
        LOGGER.info("Saving last state '%s' to cache", self._current_state)
        try:
            if not os.path.isdir(os.path.expanduser(self.config['cache_dir'])):
                os.makedirs(os.path.expanduser(self.config['cache_dir']))

            with AtomicallySavedFile(self.cache_file_path, 'w') as f:
                f.write(str(self._current_state))
        except (IOError, OSError):
            LOGGER.warning("Cannot save state to cache '%s'. ", self.cache_file_path)


    def get_cache_file_name(self):
        return self.config['source'] + ".txt"


# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
class CollectorStateMixInPlus(CollectorStateMixIn):

    """
    DO NOT USE THIS CLASS IN NEW CODE, USE ONLY CollectorWithStateMixin!

    Class for tracking state of inheriting collector.
    Holds in cache dir a file with last_state variable
    i.e. last processed ID or MD5, for instance.
    Any type casting must be done in collector.
    """

    def get_cache_file_name(self):
        return self.config['source'] + '_' + self.get_source_channel() + ".txt"


class CollectorWithStateMixin(object):

    """
    Mixin for tracking state of an inheriting collector.

    Any picklable object can be saved as a state and then be retrieved
    as an object of the same type.
    """

    def __init__(self, *args, **kwargs):
        super(CollectorWithStateMixin, self).__init__(*args, **kwargs)
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
                state = cPickle.load(cache_file)
        except (EnvironmentError, ValueError, EOFError) as exc:
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
            os.makedirs(cache_dir, 0700)
        except OSError:
            pass

        with AtomicallySavedFile(self._cache_file_path, 'wb') as f:
             cPickle.dump(state, f, cPickle.HIGHEST_PROTOCOL)
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


class BaseCollector(CollectorConfigMixin, QueuedBase, AbstractBaseCollector):

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

    # the attribute has to be overridden, if a component should
    # accept the "--n6recovery" argument option and inherits from
    # the `BaseCollector` class or its subclass
    supports_n6recovery = False

    def __init__(self, **kwargs):
        super(BaseCollector, self).__init__(**kwargs)
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
        if self.type not in RAW_TYPE_ENUMS:
            raise Exception('Wrong type of archived data in mongo: {0},'
                            '  should be one of: {1}'.format(self.type, RAW_TYPE_ENUMS))

    def update_connection_params_dict_before_run(self, params_dict):
        """
        For some collectors there may be a need to override the standard
        AMQP heartbeat interval (e.g., when collecting large files...).
        """
        super(BaseCollector, self).update_connection_params_dict_before_run(params_dict)
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
    ### (or maybe somewhere in main...)
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
             <actual data body (string)>,
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

    ## NOTE: typically, this method must be implemented in concrete subclasses
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
                The source specification string (a based on pattern:
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

    ## NOTE: typically, this method must be implemented in concrete subclasses
    def get_output_data_body(self, source, **processed_data):
        """
        Get the output AMQP message data.

        Kwargs:
            `source`:
                The source specification string (a based on pattern:
                '<source label>.<source channel>').
            <some keyword arguments>:
                Processed data (as returned by the process_input_data()
                method) passed as keyword arguments (to be specified in
                subclasses).

        Returns:
            The output AMQP message body (a string).

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
                The source specification string (a based on pattern:
                '<source label>.<source channel>').
            `output_data_body` (string):
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
        Get the output message id.

        Kwargs:
            `source`:
                The source specification string (a based on pattern:
                '<source label>.<source channel>').
            `output_data_body`:
                The output AMQP message body (a string) as returned by
                the get_output_data_body() method.
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
        return hashlib.md5('\0'.join((source,
                                      '{0:d}'.format(created_timestamp),
                                      output_data_body))
                           ).hexdigest()


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
        super(BaseOneShotCollector, self).__init__(**kwargs)
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


# TODO: migrate it to `n6datasources.collectors.base` when needed...
class BaseEmailSourceCollector(BaseOneShotCollector):

    """
    The base class for e-mail-source-based one-shot collectors.

    (Concrete subclasses are typically used in procmail-triggered scripts).
    """

    @classmethod
    def get_script_init_kwargs(cls):
        return {'input_data': {'raw_email': sys.stdin.read()}}

    def process_input_data(self, raw_email):
        return {'email_msg': ReceivedEmailMessage.from_string(raw_email)}

    def get_output_data_body(self, email_msg, **kwargs):
        """
        Extract the data body, typically from the given ReceivedEmailMessage instance.

        Kwargs:
            `email_msg`:
                An n6corelib.email_message.ReceivedEmailMessage instance.
             <other keyword arguments>:
                See: BaseCollector.get_output_data_body. Typically,
                concrete implementations will ignore them.
        """
        raise NotImplementedError

    def get_output_prop_kwargs(self, email_msg, **kwargs):
        prop_kwargs = super(BaseEmailSourceCollector,
                            self).get_output_prop_kwargs(**kwargs)
        mail_time = str(email_msg.get_utc_datetime())
        mail_subject = email_msg.get_subject()
        if 'meta' not in prop_kwargs['headers']:
            prop_kwargs['headers']['meta'] = {}
        prop_kwargs['headers']['meta']['mail_time'] = mail_time
        prop_kwargs['headers']['meta']['mail_subject'] = mail_subject
        return prop_kwargs


# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
# (use `n6datasources.collectors.base.BaseDownloadingCollector` instead)
class BaseUrlDownloaderCollector(BaseCollector):

    config_group = None
    config_required = ("source", "url", "download_timeout", "retry_timeout")

    # A list of date/time formats allowed in HTTP applications,
    # as specified by section 7.1.1.1 of RFC 7231, URL:
    # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
    _http_datetime_formats = [
        "%a, %d %b %Y %H:%M:%S GMT",     # the preferred format
        "%A, %d-%b-%y %H:%M:%S GMT",
        "%a %b %d %H:%M:%S %Y",  # (note: using '%d' here is OK, because datetime.strptime()
                                 # is lenient about '%d' vs. numbers that are *not* zero-padded,
                                 # as well as about extra spaces *between* input string elements)
    ]
    _http_last_modified_header = 'Last-Modified'

    def __init__(self, **kwargs):
        self._output_components = None
        self._http_last_modified = None
        super(BaseUrlDownloaderCollector, self).__init__(**kwargs)

    def run_handling(self):
        """
        For one-shot collectors: handle an event and return immediately.
        """
        rk, body, props = self.get_output_components(**self.input_data)
        if body:
            self._output_components = rk, body, props
            self.run()
        else:
            LOGGER.info('No data')
        LOGGER.info('Stopped')

    def get_output_components(self, **kwargs):
        """
        Clear the `_http_last_modified` attribute and call
        the parent method.
        """
        self._http_last_modified = None
        return super(BaseUrlDownloaderCollector, self).get_output_components(**kwargs)

    def get_source_channel(self, **kwargs):
        raise NotImplementedError

    def get_output_data_body(self, **kwargs):
        result = self._download_retry(self.config['url'])
        if result is not None:
            return self.process_data(result)
        else:
            raise n6CollectorException("Data download failure")

    def get_output_prop_kwargs(self, *args, **kwargs):
        properties = super(BaseUrlDownloaderCollector,
                           self).get_output_prop_kwargs(*args, **kwargs)
        if self._http_last_modified:
            if 'meta' not in properties['headers']:
                properties['headers']['meta'] = {}
            properties['headers']['meta']['http_last_modified'] = str(self._http_last_modified)
        return properties

    def process_data(self, data):
        raise NotImplementedError

    def _download_retry(self, url):
        """
        Try downloading URL until succes or timeout.

        Args:
            url: Url to download from

        Returns:
            data read from url
        """
        timeout = int(self.config['download_timeout'])
        downloaded = False
        start = datetime.datetime.utcnow()
        while not downloaded:

            auth_user = self.config.get('auth_user')
            auth_passwd = self.config.get('auth_passwd')
            data_dict_json = self.config.get('data_dict')
            if data_dict_json is not None:
                data_dict = json.loads(self.config.get('data_dict'))
            else:
                data_dict = None

            result = self._download_url(url, data_dict, auth_user, auth_passwd)

            if result is None:
                now = datetime.datetime.utcnow()
                duration = (now - start).seconds
                LOGGER.warning("Failed to download %s. Sleeping for %s seconds.",
                               url, self.config["retry_timeout"])
                if duration >= timeout:
                    LOGGER.error("Failed to download %s. Timeout exceeded.", url)
                    return None
                time.sleep(int(self.config["retry_timeout"]))
            else:
                self._try_to_set_http_last_modified(result.headers)
                downloaded = True
        return result.read()

    @classmethod
    def _download_retry_external(cls, url, timeout, retry_timeout,
                                 data_dict=None, auth_user=None, auth_passwd=None):
        downloaded = False
        start = datetime.datetime.utcnow()
        while not downloaded:

            if data_dict is not None:
                data_dict = json.loads(data_dict)
            else:
                data_dict = None

            result = cls._download_url(url, data_dict, auth_user, auth_passwd)

            if result is None:
                now = datetime.datetime.utcnow()
                duration = (now - start).seconds
                LOGGER.warning("Failed to download %s. Sleeping for %s seconds.",
                               url, retry_timeout)
                if duration >= timeout:
                    LOGGER.error("Failed to download %s. Timeout exceeded.", url)
                    return None
                time.sleep(retry_timeout)
            else:
                downloaded = True
        return result.read()

    @classmethod
    def _download_url(cls, url, data_dict=None, auth_user=None, auth_passwd=None):
        """Download data from given URL

        Args:
            url: URL
            data_dict: optional dictionary to pass in POST request
            auth_user: optional user identifier
            auth_passwd: optional user password

        Returns:
            urllib2.urlopen: data downloaded from URL
                or None when error occures
        """
        if auth_user is not None and auth_passwd is not None:
            password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, url, auth_user, auth_passwd)
            handler = urllib2.HTTPBasicAuthHandler(password_mgr)
            opener = urllib2.build_opener(handler)
        else:
            opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        if data_dict is not None:
            data_string = urllib.urlencode(data_dict)
            req = urllib2.Request(url, data_string)
        else:
            req = urllib2.Request(url)
        data = None
        try:
            data = opener.open(req, timeout=60)
        except urllib2.URLError:
            pass

        return data

    def _try_to_set_http_last_modified(self, headers):
        http_header = headers.get(self._http_last_modified_header)
        if http_header:
            for dt_format in self._http_datetime_formats:
                try:
                    parsed_datetime = datetime.datetime.strptime(http_header, dt_format)
                except ValueError:
                    pass
                else:
                    self._http_last_modified = parsed_datetime
                    break


# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
# **unless** (TODO) modernized to use `BaseDownloadingCollector`
# (instead of `BaseUrlDownloaderCollector`).
class BaseRSSCollector(BaseOneShotCollector, BaseUrlDownloaderCollector):

    type = 'stream'

    config_group = None
    config_required = ("source", "url", "cache_dir", "download_timeout", "retry_timeout")

    def __init__(self, **kwargs):
        self.last_rss = None
        self.current_rss = None
        super(BaseRSSCollector, self).__init__(**kwargs)

    def get_source_channel(self, **kwargs):
        return 'rss'

    def get_output_data_body(self, **kwargs):
        self._get_last_rss_feed()
        self.current_rss = self._process_rss(self._download_retry(self.config['url']))
        self._save_last_rss_feed()

        if self.last_rss is not None:
            diff = self.current_rss - self.last_rss
        else:
            diff = self.current_rss

        if diff:
            return json.dumps(list(diff))
        else:
            # if there are no differences publish empty Json
            return json.dumps([])

    def rss_item_to_relevant_data(self, item):
        """
        Extract the relevant data from the given RSS item.

        Args:
            `item`:
                A single item from the RSS feed.  Such an
                item is an element of a list obtained with a
                `<lxml etree/html document>.xpath(...)` call
                (see the source code of the _process_rss()
                method).

        Returns:
            Some hashable object.  It may be, for example, a
            tuple or a string -- the exact type depends on the
            implementation provided by a particular subclass
            of BaseRSSCollector.
        """
        raise NotImplementedError

    def _process_rss(self, result):
        try:
            document = lxml.etree.fromstring(result)
        except lxml.etree.XMLSyntaxError:
            document = lxml.html.fromstring(result)
        data_row_xpath = "//item"
        rows = document.xpath(data_row_xpath)
        return set(map(self.rss_item_to_relevant_data, rows))

    def _get_last_rss_feed(self):
        try:
            with open(os.path.join(os.path.expanduser(self.config['cache_dir']), "{0}.rss".format(self.config['source']))) as f:
                self.last_rss = cPickle.load(f)
        except IOError:
            self.last_rss = None
        LOGGER.info("Loaded last rss from cache")

    def _save_last_rss_feed(self):
        LOGGER.info("Saving last rss to cache")
        try:
            if not os.path.isdir(os.path.expanduser(self.config['cache_dir'])):
                os.makedirs(os.path.expanduser(self.config['cache_dir']))
            with open(os.path.join(os.path.expanduser(self.config['cache_dir']), "{0}.rss".format(self.config['source'])), "w") as f:
                cPickle.dump(self.current_rss, f)
        except (IOError, OSError):
            LOGGER.warning("Cannot save last rss to cache '%s'. "
                           "Next time full rss will be processed.",
                           os.path.join(self.config['cache_dir'],
                                        "{0}.rss".format(self.config['source'])))



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
    of rows that can be singled out (see: `split_orig_data_into_rows()`),
    selected (see: `get_fresh_rows_only()` and the methods it calls)
    and joined after all (see: `prepare_selected_data()`).

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

    ***

    Very important requirement, concerning the data source itself,
    is that values of the *time/order* field of any **new** (fresh) rows
    encountered by the collector **must** be **greater than or equal to**
    the *time/order* field's values of all rows collected during any
    previous runs of the collector.

    When it is detected that *the data source does not satisfy* the
    requirement described above:

    * if the value of the `row_count_mismatch_is_fatal` option is
      false then a warning signalling row counts mismatch is logged
      and the collector continues its work (*beware:* some rows may
      be lost, i.e., *never* collected);

    * if the value of the `row_count_mismatch_is_fatal` option is
      true then a `ValueError` is raised (the collector's activity
      is aborted; no rows are collected).

    For example, let's assume that a certain data source provided
    the following data:

        '"3", "2019-07-19 02:00:00", "sample", "data"\n'
        '"2", "2019-07-18 01:00:00", "sample_data", "data"\n'
        '"1", "2019-07-17 00:00:00", "other_data", "data"\n'

    Assuming that our imaginary collector treats the second column
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

    Even though the `4`-th and `6`-th rows could be collected, the
    `5`-th one **could not** -- as it would be considered a row *from
    the past* (as being older that the aforementioned `3`-rd row).
    Indeed, the problem is with the data source itself: it does not
    satisfy the requirement described above.

    ***

    One more thing concerning the original input data: while it is OK
    to have several rows with exact same values of the time/order field,
    whole rows should be *unique* (if duplicates are detected, a warning
    is logged or, if the `row_count_mismatch_is_fatal` option is true,
    a `ValueError` is raised; moreover, it is *not* guaranteed that such
    duplicates will be collected at all).
    """

    source_config_section = None

    config_spec_pattern = '''
        [{source_config_section}]
        source :: str
        cache_dir :: str
        row_count_mismatch_is_fatal = False :: bool
    '''

    @attr_required('source_config_section')
    def get_config_spec_format_kwargs(self):
        return {'source_config_section': self.source_config_section}


    _NEWEST_ROW_TIME_STATE_KEY = 'newest_row_time'
    _NEWEST_ROWS_STATE_KEY = 'newest_rows'
    _ROWS_COUNT_KEY = 'rows_count'


    def __init__(self, **kwargs):
        super(BaseTimeOrderedRowsCollector, self).__init__(**kwargs)
        self._state = None           # to be set in `run_handling()`
        self._selected_data = None   # to be set in `run_handling()` if needed

    def run_handling(self):
        self._state = self.load_state()
        orig_data = self.obtain_orig_data()
        all_rows = self.split_orig_data_into_rows(orig_data)
        fresh_rows = self.get_fresh_rows_only(all_rows)
        if fresh_rows:
            self._selected_data = self.prepare_selected_data(fresh_rows)
            super(BaseTimeOrderedRowsCollector, self).run_handling()

    def make_default_state(self):
        return {
            self._NEWEST_ROW_TIME_STATE_KEY: self.get_oldest_possible_row_time(),
            self._NEWEST_ROWS_STATE_KEY: set(),
            self._ROWS_COUNT_KEY: 0,
        }

    def start_publishing(self):
        self.start_iterative_publishing()

    def publish_iteratively(self):
        rk, body, prop_kwargs = self.get_output_components(selected_data=self._selected_data)
        self.publish_output(rk, body, prop_kwargs)
        yield self.FLUSH_OUT
        self.save_state(self._state)

    def get_output_data_body(self, selected_data, **kwargs):
        return selected_data


    #
    # Stuff that can be overridden in subclasses (only if needed,
    # as sensible defaults are provided -- *except* for the three
    # abstract methods: `obtain_orig_data()`, `pick_raw_row_time()`
    # and `clean_row_time()`)

    # * basic raw event attributes:

    type = 'file'
    content_type = 'text/csv'

    # * related to writable state management:

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

    # * obtaining of original data:

    def obtain_orig_data(self):
        """
        Abstract method: obtain the original raw data and return it.

        Example implementation:

            return RequestPerformer.fetch(method='GET',
                                          url=self.config['url'],
                                          retries=self.config['download_retries'])

        (Though, in practice -- when it comes to obtaining the original
        data with the `RequestPerformer` stuff -- you will more likely
        want to use the `BaseDownloadingTimeOrderedRowsCollector` class,
        rather than to implement `RequestPerformer`-based `obtain_orig_data()`
        by your own.)

        """
        raise NotImplementedError

    # * splitting original data and re-joining/preparing selected data:

    def split_orig_data_into_rows(self, orig_data):
        return orig_data.split('\n')

    def prepare_selected_data(self, fresh_rows):
        return '\n'.join(fresh_rows)

    # * selection of fresh rows:

    def get_fresh_rows_only(self, all_rows):
        prev_newest_row_time = self._state[self._NEWEST_ROW_TIME_STATE_KEY]
        prev_newest_rows = self._state[self._NEWEST_ROWS_STATE_KEY]
        # (a legacy state may not include `rows_count`)
        prev_rows_count = self._state.get(self._ROWS_COUNT_KEY)

        newest_row_time = None
        newest_rows = set()
        rows_count = 0

        fresh_rows = []

        for row in all_rows:
            row_time = self.extract_row_time(row)
            if row_time is None:
                continue

            rows_count += 1

            if row_time < prev_newest_row_time:
                # this row is old enough to assume it has already been collected
                continue

            if newest_row_time is None or row_time > newest_row_time:
                # this row time is *newer* than any of the rows already
                # processed within this run
                newest_row_time = row_time
                newest_rows.clear()

            assert row_time <= newest_row_time
            if row_time == newest_row_time:
                # this row is amongst those with the *newest* row time
                # (at least so far within this run)
                newest_rows.add(row)

            if row in prev_newest_rows:
                # this row is amongst those with the *previously newest*
                # row time, *and* it must have already been collected
                assert row_time == prev_newest_row_time
                continue

            # this row has *not* been collected yet -> let's collect it
            fresh_rows.append(row)

        self._check_counts(prev_rows_count, rows_count, fresh_rows)

        if fresh_rows:
            self._state.update({
                self._NEWEST_ROW_TIME_STATE_KEY: newest_row_time,
                self._NEWEST_ROWS_STATE_KEY: newest_rows,
                self._ROWS_COUNT_KEY: rows_count,
            })

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
                `split_orig_data_into_rows()`.

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

    def _check_counts(self, prev_rows_count, rows_count, fresh_rows):
        problems = []
        duplicated_fresh_rows_msg = "Found duplicates among fresh rows."
        invalid_rows_count_msg = (
            "The currently stated count of all rows ({}) is not equal "
            "to the sum of the count stated by the previous run of the "
            "collector ({}) and the count of the currently collected "
            "fresh rows ({})."

            "\nIt means that at least one of the following has happened:"

            "\n* the data provided by the external source has changed in "
            "such a way that the expected count of the rows which should "
            "have already been collected (according to the current data "
            "from the external source) is different than the actual count "
            "of the already collected rows (by the previous runs of the "
            "collector);"

            "\n* some fresh rows duplicate some rows collected "
            "earlier."
        ).format(rows_count, prev_rows_count, len(fresh_rows))

        if len(fresh_rows) != len(set(fresh_rows)):
            problems.append(duplicated_fresh_rows_msg)

        if prev_rows_count is not None:
            expected_rows_count = prev_rows_count + len(fresh_rows)
            if rows_count != expected_rows_count:
                problems.append(invalid_rows_count_msg)

        if problems:
            msg = '\n\nThe following problem also occurred:\n\n'.join(problems)
            if self.config['row_count_mismatch_is_fatal']:
                raise ValueError(msg)
            LOGGER.warning(msg)


class BaseDownloadingCollector(BaseCollector):

    # This constant is used only if neither config files nor
    # defaults in the config spec (if any) provide the value
    # of the `download_retries` option.
    DEFAULT_DOWNLOAD_RETRIES_IF_NOT_SPECIFIED = 10

    def __init__(self):
        super(BaseDownloadingCollector, self).__init__()
        self._http_response = None          # to be set in download()
        self._http_last_modified = None     # to be set in download()

    @property
    def http_response(self):
        return self._http_response

    @property
    def http_last_modified(self):
        return self._http_last_modified

    def download(self,
                 url,
                 method='GET',
                 retries=None,
                 custom_request_headers=None,
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
            return perf.response.content

    def _get_request_retries(self, retries):
        if retries is None:
            retries = self.config.get('download_retries',
                                      self.DEFAULT_DOWNLOAD_RETRIES_IF_NOT_SPECIFIED)
        return retries

    def _get_request_headers(self, custom_request_headers):
        base_request_headers = self.config.get('base_request_headers', {})
        if not isinstance(base_request_headers, dict):
            raise ConfigError('config option `base_request_headers` '
                              'is not a dict: {!r}'.format(base_request_headers))
        headers = base_request_headers.copy()
        if custom_request_headers:
            headers.update(custom_request_headers)
        return headers

    def get_output_prop_kwargs(self, **processed_data):
        prop_kwargs = super(BaseDownloadingCollector,
                            self).get_output_prop_kwargs(**processed_data)
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
        row_count_mismatch_is_fatal = False :: bool
    '''

    def obtain_orig_data(self):
        return self.download(self.config['url'])



#
# Script/entry point factories

# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
# (replaced by `n6datasources.collectors.base.AbstractBaseCollector.run_script()`)
def generate_collector_main(collector_class):
    def collector_main():
        with logging_configured():
            init_kwargs = collector_class.get_script_init_kwargs()
            collector = collector_class(**init_kwargs)
            collector.run_handling()
    return collector_main

# LEGACY STUFF -- we DO NOT want to migrate it to n6datasources...
# (use `n6datasources.collectors.base.add_collector_entry_point_functions()` instead)
def entry_point_factory(module):
    for collector_class in all_subclasses(AbstractBaseCollector):
        if (not collector_class.__module__.endswith('.generic') and
              not collector_class.__name__.startswith('_')):
            setattr(module, "%s_main" % collector_class.__name__,
                    generate_collector_main(collector_class))

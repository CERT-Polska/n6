# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

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

import lxml.etree
import lxml.html

from n6lib.config import (
    ConfigMixin,
    ConfigSection,
)
from n6.base.queue import QueuedBase
from n6lib.class_helpers import all_subclasses
from n6lib.common_helpers import ascii_str
from n6lib.email_message import EmailMessage
from n6lib.log_helpers import get_logger, logging_configured


LOGGER = get_logger(__name__)


#
# Exceptions

class n6CollectorException(Exception):
    pass


#
# Mixin classes

class CollectorConfigMixin(ConfigMixin):

    config_spec_format_kwargs = None

    def set_configuration(self):
        if self.is_config_spec_or_group_declared():
            format_kwargs = (self.config_spec_format_kwargs
                             if self.config_spec_format_kwargs is not None
                             else {})
            self.config = self.get_config_section(**format_kwargs)
        else:
            # backward-compatible behavior needed by a few collectors
            # that have `config_group = None` and -- at the same
            # time -- no `config_spec`/`config_spec_pattern`
            self.config = ConfigSection('<no section declared>')


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
            with open(self.cache_file_path, "w") as f:
                f.write(str(self._current_state))
        except (IOError, OSError):
            LOGGER.warning("Cannot save state to cache '%s'. ", self.cache_file_path)

    def get_cache_file_name(self):
        return self.config['source'] + ".txt"


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
            LOGGER.warning(
                "Could not load state, returning None (%s: %s)",
                exc.__class__.__name__,
                ascii_str(exc))
            state = None
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
        with open(self._cache_file_path, 'wb') as cache_file:
            cPickle.dump(state, cache_file, cPickle.HIGHEST_PROTOCOL)
        LOGGER.info("Saved state: %r", state)

    def get_cache_file_name(self):
        source_channel = self.get_source_channel()
        source = self.get_source(source_channel=source_channel)
        return '{}.{}.pickle'.format(source, self.__class__.__name__)


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
    limits_type_of = ('stream', 'file', 'blacklist')

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

    def _validate_type(self):
        """Validate type of mesage, should be one of: 'stream', 'file', 'blacklist."""
        if self.type not in self.limits_type_of:
            raise Exception('Wrong type of archived data in mongo: {0},'
                            '  should be one of: {1}'.format(self.type, self.limits_type_of))

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
        created_timestamp = int(time.time())
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

    @staticmethod
    def get_output_message_id(source, created_timestamp,
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
                Message creation timestamp as a float number.
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


class BaseEmailSourceCollector(BaseOneShotCollector):

    """
    The base class for e-mail-source-based one-shot collectors.

    (Concrete subclasses are typically used in procmail-triggered scripts).
    """

    class NoMatchingRegexException(Exception):
        """
        Raised when a searched regex pattern was not found in e-mail's
        body.
        """

    @classmethod
    def get_script_init_kwargs(cls):
        return {'input_data': {'raw_email': sys.stdin.read()}}

    def process_input_data(self, raw_email):
        return {'email_msg': EmailMessage.from_string(raw_email)}

    def get_output_data_body(self, email_msg, **kwargs):
        """
        Extract the data body, typically from the given EmailMessage instance.

        Kwargs:
            `email_msg`:
                An n6lib.email_message.EmailMessage instance.
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


def generate_collector_main(collector_class):
    def parser_main():
        with logging_configured():
            init_kwargs = collector_class.get_script_init_kwargs()
            collector = collector_class(**init_kwargs)
            collector.run_handling()
    return parser_main


def entry_point_factory(module):
    for collector_class in all_subclasses(AbstractBaseCollector):
        if (not collector_class.__module__.endswith('.generic') and
              not collector_class.__name__.startswith('_')):
            setattr(module, "%s_main" % collector_class.__name__,
                    generate_collector_main(collector_class))

# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import collections
import contextlib
import functools
import json
import logging
import logging.config
import logging.handlers
import os.path
import Queue
import re
import repr as reprlib
import sys
import threading
import traceback

from pika.exceptions import AMQPConnectionError

from n6lib.amqp_getters_pushers import AMQPThreadedPusher, DoNotPublish
from n6lib.common_helpers import (
    ascii_str,
    dump_condensed_debug_msg,
    make_condensed_debug_msg,
    safe_eval,
)
from n6lib.const import (
    ETC_DIR,
    HOSTNAME,
    USER_DIR,
    SCRIPT_BASENAME,
    TOPLEVEL_N6_PACKAGES,
)


#
# Logging preparation'n'configuration

def early_Formatter_class_monkeypatching():  # called in n6lib/__init__.py
    """
    Do logging.Formatter monkey-patching to use *always* UTC time.
    """
    from time import gmtime, strftime

    @functools.wraps(logging.Formatter.formatTime.__func__)
    def formatTime(self, record, datefmt=None):
        converter = self.converter
        ct = converter(record.created)
        if datefmt:
            s = strftime(datefmt, ct)
        else:
            t = strftime("%Y-%m-%d %H:%M:%S", ct)
            s = "%s,%03d" % (t, record.msecs)
        if converter is gmtime:
            # the ' UTC' suffix is added *only* if it
            # is certain that we have a UTC time
            s += ' UTC'
        else:
            s += ' <UNCERTAIN TIMEZONE>'
        return s

    logging.Formatter.converter = gmtime
    logging.Formatter.formatTime = formatTime


def get_logger(name=None):
    """
    Like logging.getLogger(...) but replacing '__main__' with a sensible name.

    For example, if the script path is '/whatever/n6/utils/foo.py'
    get_logger('__main__') is equivalent to logging.getLogger('n6.utils.foo').
    """
    if name == '__main__':
        # try to get the script path from __main__.__file__
        script_path = getattr(sys.modules['__main__'], '__file__', None)
        if not script_path:
            # or, if __main__ does not have a non-blank __file__ attribute,
            # extract the script path from sys.argv...
            script_path = sys.argv[0]
        # strip off the filename extension...
        remaining = os.path.splitext(script_path)[0]
        # ..and pop path name segments up to
        # (and including) the n6 toplevel package name
        aggregated_segments = collections.deque()
        while True:
            remaining, segment = os.path.split(remaining)
            segment = segment.replace('.', 'D')  # just in case of '.' or '..'
            aggregated_segments.appendleft(segment)
            if segment in TOPLEVEL_N6_PACKAGES or remaining in ('', '/'):
                break
        name = '.'.join(aggregated_segments)
    return logging.getLogger(name)


_LOGGER = get_logger(__name__)

_loaded_configuration_paths = set()

# TODO: doc
def configure_logging(suffix=None):
    logging.config.eval = _security_logging_config_monkeypatched_eval
    file_name = ('logging.conf' if suffix is None
                 else 'logging-{0}.conf'.format(suffix))
    file_paths = [os.path.join(config_dir, file_name)
                  for config_dir in (ETC_DIR, USER_DIR)]
    for path in file_paths:
        if path in _loaded_configuration_paths:
            _LOGGER.warning('ignored attempt to load logging configuration '
                            'file %r that has already been used', path)
            continue
        try:
            _try_reading(path)
        except EnvironmentError:
            pass
        else:
            try:
                logging.config.fileConfig(path, disable_existing_loggers=False)

            except AMQPConnectionError:
                raise RuntimeError('error while configuring logging, '
                                   'using settings from configuration file {0!r}:\n'
                                   'unable to establish '
                                   'connection with RabbitMQ server\n{1}'
                                   .format(path, traceback.format_exc()))
            except Exception:
                raise RuntimeError('error while configuring logging, '
                                   'using settings from configuration file {0!r}:\n{1}'
                                   .format(path, traceback.format_exc()))
            else:
                _LOGGER.info('logging configuration loaded from %r', path)
                _loaded_configuration_paths.add(path)
    if not _loaded_configuration_paths:
        raise RuntimeError('logging configuration not loaded: '
                           'could not open any of the files: {0}'
                           .format(', '.join(map(repr, file_paths))))


# TODO: doc and maybe some tests?
@contextlib.contextmanager
def logging_configured(suffix=None):
    configure_logging(suffix)
    try:
        yield
    except SystemExit as exc:
        if exc.code:
            _LOGGER.critical(
                "SystemExit(%r) occurred (debug info: %s). Exiting...",
                exc.code, make_condensed_debug_msg(), exc_info=True)
            dump_condensed_debug_msg()
        else:
            _LOGGER.info(
                "SystemExit(%r) occurred. Exiting...",
                exc.code)
        raise
    except KeyboardInterrupt:
        _LOGGER.warning("KeyboardInterrupt occurred. Exiting...")
        sys.exit(1)
    except:
        _LOGGER.critical(
            'Irrecoverable problem (debug info: %s). Exiting...',
            make_condensed_debug_msg(), exc_info=True)
        dump_condensed_debug_msg()
        raise


def _try_reading(path):
    open(path).close()


# TODO?: maybe some tests?
def _security_logging_config_monkeypatched_eval(expr, namespace_dict):
    """
    More secure replacement for eval() used by some logging.config functions.
    """
    namespace = dict(namespace_dict)
    try:
        return safe_eval(expr, namespace)
    except ValueError:
        raise NameError  # to be catched by logging.config machinery


#
# Custom log handlers

# TODO: doc
class AMQPHandler(logging.Handler):

    ERROR_LOGGER = 'AMQP_LOGGING_HANDLER_ERRORS'
    LOGRECORD_EXTRA_ATTRS = {
        'py_ver': '.'.join(map(str, sys.version_info)),
        'py_64bits': (sys.maxsize > 2 ** 32),
        'py_ucs4': (sys.maxunicode > 0xffff),
        'py_platform': sys.platform,
        'hostname': HOSTNAME,
        'script_basename': SCRIPT_BASENAME,
    }

    DEFAULT_MSG_COUNT_WINDOW = 300
    DEFAULT_MSG_COUNT_MAX = 100

    DEFAULT_EXCHANGE_DECLARE_KWARGS = {'exchange_type': 'topic'}
    DEFAULT_RK_TEMPLATE = '{hostname}.{script_basename}.{levelname}.{loggername}'
    DEFAULT_PROP_KWARGS = dict(
        content_type='application/json',
        delivery_mode=1,
    )

    def __init__(self, connection_params_dict,
                 exchange='logging',
                 exchange_declare_kwargs=None,
                 rk_template=None,
                 prop_kwargs=None,
                 other_pusher_kwargs=None,
                 error_logger_name=None,
                 msg_count_window=None,
                 msg_count_max=None,
                 **super_kwargs):
        if exchange_declare_kwargs is None:
            exchange_declare_kwargs = self.DEFAULT_EXCHANGE_DECLARE_KWARGS
        if rk_template is None:
            rk_template = self.DEFAULT_RK_TEMPLATE
        if prop_kwargs is None:
            prop_kwargs = self.DEFAULT_PROP_KWARGS
        if other_pusher_kwargs is None:
            other_pusher_kwargs = {}
        if error_logger_name is None:
            error_logger_name = self.ERROR_LOGGER
        if msg_count_window is None:
            msg_count_window = self.DEFAULT_MSG_COUNT_WINDOW
        if msg_count_max is None:
            msg_count_max = self.DEFAULT_MSG_COUNT_MAX

        super(AMQPHandler, self).__init__(**super_kwargs)

        self._rk_template = rk_template
        self._msg_count_window = msg_count_window
        self._msg_count_max = msg_count_max

        # error logging tools
        self._error_fifo = error_fifo = Queue.Queue()
        self._error_logger_name = error_logger_name
        self._error_logging_thread = threading.Thread(
            target=self._error_logging_loop,
            kwargs=dict(error_fifo=self._error_fifo,
                        error_logger=logging.getLogger(error_logger_name)))
        self._error_logging_thread.daemon = True
        self._closing = False

        def error_callback(exc):
            try:
                exc_info = sys.exc_info()
                assert exc_info[1] is exc
                error_msg = make_condensed_debug_msg(exc_info)
                error_fifo.put_nowait(error_msg)
            finally:
                # (to break any traceback-related reference cycle)
                exc_info = None

        # pusher instance
        self._pusher = AMQPThreadedPusher(
            connection_params_dict=connection_params_dict,
            exchange=dict(exchange_declare_kwargs,
                          exchange=exchange),
            prop_kwargs=prop_kwargs,
            serialize=self._make_record_serializer(),
            error_callback=error_callback,
            **other_pusher_kwargs)

        # start error logging co-thread
        self._error_logging_thread.start()

    @classmethod
    def _error_logging_loop(cls, error_fifo, error_logger):
        try:
            while True:
                error_msg = error_fifo.get()
                error_logger.error('%s', error_msg)
        except:
            dump_condensed_debug_msg('ERROR LOGGING CO-THREAD STOPS WITH EXCEPTION!')
            raise   # traceback should be printed to sys.stderr automatically


    def _make_record_serializer(self):
        defaultdict = collections.defaultdict
        formatter = logging.Formatter()
        json_encode = json.JSONEncoder(default=reprlib.repr).encode
        record_attrs_proto = self.LOGRECORD_EXTRA_ATTRS
        match_useless_stack_item_regex = re.compile(
                r'  File "[ \S]*/python[0-9.]+/logging/__init__\.py\w?"'
            ).match

        msg_count_window = self._msg_count_window
        msg_count_max = self._msg_count_max
        cur_window_cell = [None]  # using 1-item list as a cell for a writable non-local variable
        loggername_to_window_and_msg_to_count = defaultdict(
            lambda: (cur_window_cell[0], defaultdict(
                lambda: -msg_count_max)))

        def _should_publish(record):
            # if, within the particular time window (window length is
            # defined as `msg_count_window`, in seconds), the number of
            # records from the particular logger that contain the same
            # `msg` (note: *not* necessarily the same `message`!)
            # exceeds the limit (defined as `msg_count_max`) --
            # further records containing that `msg` and originating from
            # that logger are skipped until *any* record from that
            # logger appears within *another* time window...
            loggername = record.name
            msg = record.msg
            cur_window_cell[0] = cur_window = record.created // msg_count_window
            window, msg_to_count = loggername_to_window_and_msg_to_count[loggername]
            if window != cur_window:
                # new time window for this logger
                # => attach (as the `msg_skipped_to_count` record
                #    attribute) the info about skipped messages (if
                #    any) and update/flush the state mappings
                msg_skipped_to_count = dict(
                    (m, c) for m, c in msg_to_count.iteritems()
                    if c > 0)
                if msg_skipped_to_count:
                    record.msg_skipped_to_count = msg_skipped_to_count
                loggername_to_window_and_msg_to_count[loggername] = cur_window, msg_to_count
                msg_to_count.clear()
            msg_to_count[msg] = count = msg_to_count[msg] + 1
            if count <= 0:
                if count == 0:
                    # this is the last record (from the particular
                    # logger + containing the particular `msg`) in
                    # the current time window that is *not* skipped
                    # => so it obtains the `msg_reached_count_max`
                    #    attribute (equal to `msg_count_max` value)
                    record.msg_reached_count_max = msg_count_max
                return True
            else:
                return False

        def serialize_record(record):
            if not _should_publish(record):
                return DoNotPublish
            record_attrs = record_attrs_proto.copy()
            record_attrs.update(vars(record))
            record_attrs['message'] = record.getMessage()
            record_attrs['asctime'] = formatter.formatTime(record)
            exc_info = record_attrs.pop('exc_info', None)
            if exc_info:
                if not record_attrs['exc_text']:
                    record_attrs['exc_text'] = formatter.formatException(exc_info)
                record_attrs['exc_type_repr'] = repr(exc_info[0])
                record_attrs['exc_ascii_str'] = ascii_str(exc_info[1])
            stack_items = record_attrs.pop('formatted_call_stack_items', None)
            if stack_items:
                del stack_items[-1]  # this item is from this AMQPHandler.emit()
                while stack_items and match_useless_stack_item_regex(stack_items[-1]):
                    del stack_items[-1]
                record_attrs['formatted_call_stack'] = ''.join(stack_items)
            return json_encode(record_attrs)

        return serialize_record


    def emit(self, record, _ERROR_LEVEL_NO=logging.ERROR):
        try:
            # ignore internal AMQP-handler-related error messages --
            # i.e., those logged with the handler's error logger
            # (to avoid infinite loop of message emissions...)
            if record.name == self._error_logger_name:
                return
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logging.Handler.handleError(self, record)

        try:
            if record.levelno >= _ERROR_LEVEL_NO:
                record.formatted_call_stack_items = traceback.format_stack()
            routing_key = self._rk_template.format(
                hostname=HOSTNAME,
                script_basename=SCRIPT_BASENAME,
                levelname=record.levelname,
                loggername=record.name)
            try:
                self._pusher.push(record, routing_key)
            except ValueError:
                if not self._closing:
                    raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        # typically, this method is called at interpreter exit
        # (by logging.shutdown() which is always registered with
        # atexit.register() machinery)
        try:
            try:
                super(AMQPHandler, self).close()
                self._closing = True
                self._pusher.shutdown()
            except:
                dump_condensed_debug_msg(
                    'EXCEPTION DURING EXECUTION OF close() OF THE AMQP LOGGING HANDLER!')
                raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exc = sys.exc_info()[1]
            self._error_fifo.put(exc)

    def handleError(self, record):
        try:
            exc = sys.exc_info()[1]
            self._error_fifo.put(exc)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logging.Handler.handleError(self, record)


class N6SysLogHandler(logging.handlers.SysLogHandler):

    def emit(self, record):
        record.script_basename = SCRIPT_BASENAME
        super(N6SysLogHandler, self).emit(record)


#
# Custom log formatters

class NoTracebackFormatter(logging.Formatter):

    r"""
    >>> fmt='* %(message)s *'
    >>> std_formatter = logging.Formatter(fmt)
    >>> ntb_formatter = NoTracebackFormatter(fmt)
    >>> record = logging.LogRecord('mylog', 10, '/', 997,
    ...                            msg='error: %r', args=(42,),
    ...                            exc_info=(ValueError,
    ...                                      ValueError('Traceback!!!!!!!!!!!!'),
    ...                                      None))

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'

    >>> ntb_formatter.format(record)
    '* error: 42 *'
    """

    # Unfortunatelly overriding formatException() would not be adequate
    # because of a subtle bug in logging.Formatter.format() in the
    # mechanism of caching of record.exc_text...

    def format(self, record):
        # here we substitute logging.Formatter.format()'s functionality
        # with its fragment (omitting the exc_info stuff):
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        return self._fmt % record.__dict__


class CutFormatter(logging.Formatter):

    r"""
    >>> fmt='* %(message)s *'
    >>> std_formatter = logging.Formatter(fmt)
    >>> cut_formatter = CutFormatter(fmt,
    ...                              msg_length_limit=4,
    ...                              cut_indicator='... [!]')
    >>> record = logging.LogRecord('mylog', 10, '/', 997,
    ...                            msg='error: %r', args=(42,),
    ...                            exc_info=(ValueError,
    ...                                      ValueError('Traceback!!!!!!!!!!!!'),
    ...                                      None))

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'

    >>> cut_formatter.format(record)
    '* erro... [!] *\nValueError: Traceback!!!!!!!!!!!!'
    """

    DEFAULT_MSG_LENGTH_LIMIT = 2000
    DEFAULT_CUT_INDICATOR = '... <- cut!!!'

    def __init__(self, *args, **kwargs):
        self.msg_length_limit = kwargs.pop('msg_length_limit', self.DEFAULT_MSG_LENGTH_LIMIT)
        self.cut_indicator = kwargs.pop('cut_indicator', self.DEFAULT_CUT_INDICATOR)
        super(CutFormatter, self).__init__(*args, **kwargs)

    def format(self, record):
        record_proxy = _LogRecordCuttingProxy(record,
                                              self.msg_length_limit,
                                              self.cut_indicator)
        return super(CutFormatter, self).format(record_proxy)


class NoTracebackCutFormatter(CutFormatter, NoTracebackFormatter):
    r"""
    >>> fmt='* %(message)s *'
    >>> std_formatter = logging.Formatter(fmt)
    >>> ntb_cut_formatter = NoTracebackCutFormatter(fmt,
    ...                                             msg_length_limit=4,
    ...                                             cut_indicator='... [!]')
    >>> record = logging.LogRecord('mylog', 10, '/', 997,
    ...                            msg='error: %r', args=(42,),
    ...                            exc_info=(ValueError,
    ...                                      ValueError('Traceback!!!!!!!!!!!!'),
    ...                                      None))

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'

    >>> ntb_cut_formatter.format(record)
    '* erro... [!] *'
    """


# A private helper class for CutFormatter:

class _LogRecordCuttingProxy(object):

    def __init__(self, record, msg_length_limit, cut_indicator):
        # inner attribute names start with '__' => Python name mangling in use
        self.__record = record
        self.__msg_length_limit = msg_length_limit
        self.__cut_indicator = cut_indicator
        self.__already_cut = {'thread_safe_flag': False}

    def __delattr__(self, name, obj):
        delattr(self.__record, name, obj)

    def __setattr__(self, name, obj):
        if name.startswith('_LogRecordCuttingProxy__'):  # mangled name
            object.__setattr__(self, name, obj)
        else:
            setattr(self.__record, name, obj)

    def __getattribute__(self, name):
        if name.startswith('_LogRecordCuttingProxy__'):  # mangled name
            return object.__getattribute__(self, name)

        # for attributes other than `message` act as a transparent proxy
        record = self.__record
        if name not in ('message', '__dict__'):
            return getattr(record, name)

        # if the message has already been cut
        # -- get it quickly; otherwise cut it
        if not self.__already_cut.pop('thread_safe_flag', True):
            msg_length_limit = self.__msg_length_limit
            if len(record.message) > msg_length_limit:
                record.message = record.message[:msg_length_limit] + self.__cut_indicator
        if name == '__dict__':
            return record.__dict__
        else:
            return record.message

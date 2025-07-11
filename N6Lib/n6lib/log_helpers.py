# Copyright (c) 2013-2024 NASK. All rights reserved.

import collections
import contextlib
import functools
import inspect
import json
import logging
import logging.config
import logging.handlers
import os.path
import queue
import re
import reprlib
import sys
import threading
import traceback

from pika.exceptions import AMQPConnectionError

from n6lib.common_helpers import (
    ascii_str,
    dump_condensed_debug_msg,
    limit_str,
    make_condensed_debug_msg,
)
from n6lib.const import (
    ETC_DIR,
    HOSTNAME,
    USER_DIR,
    SCRIPT_BASENAME,
)


# To be imported from `n6lib.amqp_getters_pushers` when actually needed
# in `AMQPHandler.__init__()` (not here, to avoid a circular import).
AMQPThreadedPusher = DoNotPublish = None


#
# Logging preparation'n'configuration

def early_Formatter_class_monkeypatching():  # called in n6lib/__init__.py
    """
    Do logging.Formatter monkey-patching to use *always* UTC time.
    """
    from time import gmtime, strftime

    @functools.wraps(logging.Formatter.formatTime)
    def formatTime(self, record, datefmt=None):
        converter = self.converter
        ct = converter(record.created)
        if datefmt:
            s = strftime(datefmt, ct)
        else:
            s = strftime(self.default_time_format, ct)
            if self.default_msec_format:
                s = self.default_msec_format % (s, record.msecs)
        if converter is gmtime:
            # the ' UTC' suffix is added *only* if it
            # is certain that we have a UTC time
            s += ' UTC'
        else:
            s += ' <UNCERTAIN TIMEZONE>'
        return s

    logging.Formatter.converter = gmtime
    logging.Formatter.formatTime = formatTime


get_logger = logging.getLogger  # This alias exists for historical reasons...


_LOGGER = get_logger(__name__)

_loaded_configuration_paths = set()

# TODO: doc
def configure_logging(suffix=None):
    file_name = ('logging.conf' if suffix is None
                 else 'logging-{0}.conf'.format(suffix))
    file_paths = [os.path.join(config_dir, file_name)
                  for config_dir in (ETC_DIR, USER_DIR)]
    for path in file_paths:
        if path in _loaded_configuration_paths:
            _LOGGER.warning('ignored attempt to load logging configuration '
                            'file %a that has already been used', path)
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
                                   'using settings from configuration file {0!a}:\n'
                                   'unable to establish '
                                   'connection with RabbitMQ server\n{1}'
                                   .format(path, traceback.format_exc()))
            except Exception:
                raise RuntimeError('error while configuring logging, '
                                   'using settings from configuration file {0!a}:\n{1}'
                                   .format(path, traceback.format_exc()))
            else:
                _LOGGER.info('logging configuration loaded from %a', path)
                _loaded_configuration_paths.add(path)
    if not _loaded_configuration_paths:
        raise RuntimeError('logging configuration not loaded: '
                           'could not open any of the files: {0}'
                           .format(', '.join(map(ascii, file_paths))))


# TODO: doc and maybe some tests?
# TODO: consider rename + move it somewhere else (`script_helpers`...?)
@contextlib.contextmanager
def logging_configured(suffix=None):
    configure_logging(suffix)
    try:
        yield
    except SystemExit as exc:
        if exc.code:
            _LOGGER.critical(
                "SystemExit(%a) occurred (debug info: %s). Exiting...",
                exc.code, make_condensed_debug_msg(), exc_info=True)
            dump_condensed_debug_msg()
        else:
            _LOGGER.info(
                "SystemExit(%a) occurred. Exiting...",
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


#
# Custom log handlers

# TODO: doc
class AMQPHandler(logging.Handler):

    ERROR_LOGGER = 'AMQP_LOGGING_HANDLER_ERRORS'
    LOGRECORD_EXTRA_ATTRS = {
        'py_ver': '.'.join(map(str, sys.version_info)),
        'py_64bits': (sys.maxsize > 2 ** 32),
        'py_platform': sys.platform,
        'hostname': HOSTNAME,
        'script_basename': SCRIPT_BASENAME,
    }
    LOGRECORD_KEY_MAX_LENGTH = 256

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

        global AMQPThreadedPusher, DoNotPublish
        if AMQPThreadedPusher is None:
            assert DoNotPublish is None
            from n6lib.amqp_getters_pushers import AMQPThreadedPusher, DoNotPublish
        assert AMQPThreadedPusher is not None
        assert DoNotPublish is not None

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
        self._error_fifo = error_fifo = queue.Queue()
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
                exc_info = exc = None  # noqa

        if isinstance(connection_params_dict, dict):
            connection_params_dict = self._get_actual_conn_params_dict(connection_params_dict)

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

    def _get_actual_conn_params_dict(self, given_dict):
        # (avoiding error related to circular imports...)
        from n6lib.amqp_helpers import get_amqp_connection_params_dict_from_args

        warn = functools.partial(
            print,
            '\n*** WARNING: ***',
            sep='\n\n',
            end='\n\n',
            file=sys.stderr,
        )
        if self._is_in_modern_format(given_dict):
            with get_amqp_connection_params_dict_from_args.set_log_warning_func(warn):
                prepared_dict = get_amqp_connection_params_dict_from_args(**given_dict)
            return prepared_dict
        warn(
            (
                'The dict obtained by the AMQPHandler constructor as '
                'its first argument seems to be in the legacy format, '
                'so (keeping the legacy behavior) no errors will be '
                'raised and no warnings will be printed if the content '
                'of that dict suffers from certain kinds of problems...'
            ),
            (
                'Please, consider making that argument be specified '
                'using the modern format, i.e., as a dict of **kwargs '
                'ready to be passed to the function n6lib.amqp_helpers.'
                'get_amqp_connection_params_dict_from_args().'
            ),
            (
                'The support for the legacy format will be dropped in '
                'a future version of *n6*.'
            ),
        )
        return given_dict

    def _is_in_modern_format(self, given_dict):
        # Is it a dict of **kwargs ready to be passed to the
        # function get_amqp_connection_params_dict_from_args()`?

        # (avoiding error related to circular imports...)
        from n6lib.amqp_helpers import get_amqp_connection_params_dict_from_args

        sig = inspect.signature(get_amqp_connection_params_dict_from_args)
        try:
            sig.bind(**given_dict)
        except TypeError:
            return False
        return True


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
        assert DoNotPublish is not None
        _DoNotPublish = DoNotPublish
        defaultdict = collections.defaultdict
        formatter = logging.Formatter()
        json_encode = json.JSONEncoder(default=reprlib.repr).encode
        record_attrs_proto = self.LOGRECORD_EXTRA_ATTRS
        record_key_max_length = self.LOGRECORD_KEY_MAX_LENGTH
        match_useless_stack_item_regex = re.compile(
                r'  File "[ \S]*/python[0-9.]+/logging/__init__\.py\w?"',
                re.ASCII,
            ).match
        # (see: https://github.com/python/cpython/blob/4f161e65a011f287227c944fad9987446644041f/Lib/logging/__init__.py#L1540)
        stack_info_preamble = 'Stack (most recent call last):\n'

        msg_count_window = self._msg_count_window
        msg_count_max = self._msg_count_max
        cur_window = None
        loggername_to_window_and_msg_to_count = defaultdict(
            lambda: (cur_window, defaultdict(
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
            nonlocal cur_window
            loggername = record.name
            msg = record.msg
            cur_window = record.created // msg_count_window
            window, msg_to_count = loggername_to_window_and_msg_to_count[loggername]
            if window != cur_window:
                # new time window for this logger
                # => attach (as the `msg_skipped_to_count` record
                #    attribute) the info about skipped messages (if
                #    any) and update/flush the state mappings
                msg_skipped_to_count = dict(
                    (m, c) for m, c in msg_to_count.items()
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

        def _try_to_extract_formatted_call_stack(record_attrs):
            # Provided by standard `logging` stuff if log method was called with `stack_info=True`:
            stack_info = record_attrs.pop('stack_info', None)
            # Provided by our `AMQPHandler.emit()` if `levelno` was at least `logging.ERROR` and
            # `stack_info` was not present:
            stack_items = record_attrs.pop('formatted_call_stack_items', None)
            if stack_items:
                del stack_items[-1]  # (this item is from our `AMQPHandler.emit()`)
                while stack_items and match_useless_stack_item_regex(stack_items[-1]):
                    del stack_items[-1]
                joined = ''.join(stack_items)
                # (mimicking how `stack_info` is formatted by `logging`)
                if joined.endswith('\n'):
                    joined = joined[:-1]
                formatted_call_stack = stack_info_preamble + joined
            elif stack_info:
                # (`stack_info` should already start with `stack_info_preamble`)
                formatted_call_stack = stack_info
            else:
                formatted_call_stack = None
            return formatted_call_stack

        def serialize_record(record):
            if not _should_publish(record):
                return _DoNotPublish
            record_attrs = record_attrs_proto.copy()
            record_attrs.update((limit_str(ascii_str(key),
                                           char_limit=record_key_max_length),
                                 value)
                                for key, value in vars(record).items())
            record_attrs['message'] = record.getMessage()
            record_attrs['asctime'] = formatter.formatTime(record)
            exc_info = record_attrs.pop('exc_info', None)
            if exc_info:
                if not record_attrs['exc_text']:
                    record_attrs['exc_text'] = formatter.formatException(exc_info)
                record_attrs['exc_type_repr'] = ascii(exc_info[0])
                record_attrs['exc_ascii_str'] = ascii_str(exc_info[1])
            formatted_call_stack = _try_to_extract_formatted_call_stack(record_attrs)
            if formatted_call_stack:
                record_attrs['formatted_call_stack'] = formatted_call_stack
            return json_encode(record_attrs)

        return serialize_record


    def emit(self, record, _ERROR_LEVEL_NO=logging.ERROR):
        try:
            # ignore internal AMQP-handler-related error messages --
            # i.e., those logged with the handler's error logger
            # (to avoid infinite loop of message emissions...)
            if record.name == self._error_logger_name:
                return
            # (exception here ^ is hardly probable, but you never know...)
        except RecursionError:  # see: https://bugs.python.org/issue36272 XXX: is it really needed?
            raise
        except Exception:
            super().handleError(record)
            # (better trigger the same exception again than continue
            # if the following condition is true)
            if record.name == self._error_logger_name:
                return

        try:
            if record.levelno >= _ERROR_LEVEL_NO and not record.stack_info:
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
        except RecursionError:  # see: https://bugs.python.org/issue36272 XXX: is it really needed?
            raise
        except Exception:
            self.handleError(record)

    def close(self):
        # typically, this method is called at interpreter exit
        # (by logging.shutdown() which is always registered with
        # atexit.register() machinery)
        try:
            try:
                try:
                    super(AMQPHandler, self).close()
                finally:
                    self._closing = True
                    self._pusher.shutdown()
            except:
                dump_condensed_debug_msg(
                    'EXCEPTION DURING EXECUTION OF close() OF THE AMQP LOGGING HANDLER!')
                raise
        except Exception as exc:
            self._error_fifo.put(exc)
        finally:
            # (to break any traceback-related reference cycle)
            self = None  # noqa

    def handleError(self, record):
        try:
            exc = sys.exc_info()[1]
            self._error_fifo.put(exc)
        except RecursionError:  # see: https://bugs.python.org/issue36272 XXX: is it really needed?
            raise
        except Exception:
            super().handleError(record)
        else:
            super().handleError(record)
        finally:
            # (to break any traceback-related reference cycle)
            exc = self = None  # noqa


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
    ...                                      None))   # TODO: add `stack_info` str do this doctest

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'

    >>> ntb_formatter.format(record)
    '* error: 42 *'
    """

    # Unfortunately, overriding formatException() would not be adequate
    # because of a subtle bug in logging.Formatter.format() in the
    # mechanism of caching of record.exc_text...

    def format(self, record):
        # here we substitute logging.Formatter.format()'s functionality with
        # its fragment (omitting the `exc_info`/`exc_text`/`stack_info` stuff):
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        return self.formatMessage(record)


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
    ...                                      None))   # TODO: add `stack_info` str do this doctest

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'

    >>> cut_formatter.format(record)
    '* erro... [!] *\nValueError: Traceback!!!!!!!!!!!!'

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'
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
    ...                                      None))   # TODO: add `stack_info` str do this doctest

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'

    >>> ntb_cut_formatter.format(record)
    '* erro... [!] *'

    >>> std_formatter.format(record)
    '* error: 42 *\nValueError: Traceback!!!!!!!!!!!!'
    """


# A private helper class for CutFormatter:

class _LogRecordCuttingProxy(object):

    def __init__(self, record, msg_length_limit, cut_indicator):
        # inner attribute names start with '__' => Python name mangling in use
        self.__record = record
        self.__msg_length_limit = msg_length_limit
        self.__cut_indicator = cut_indicator
        self.__already_cut = {'thread_safe_flag': False}

    def __repr__(self):
        return ('{cls.__qualname__}'
                '({record!r},'
                ' {msg_length_limit!r},'
                ' {cut_indicator!r})'.format(
                        cls=type(self),
                        record=self.__record,
                        msg_length_limit=self.__msg_length_limit,
                        cut_indicator=self.__cut_indicator))

    def __delattr__(self, name):
        delattr(self.__record, name)

    def __setattr__(self, name, obj):
        if name.startswith('_LogRecordCuttingProxy__'):  # mangled name
            object.__setattr__(self, name, obj)
        else:
            setattr(self.__record, name, obj)

    def __getattribute__(self, name):
        if (name.startswith('_LogRecordCuttingProxy__')  # mangled name
              or name == '__repr__'):
            return object.__getattribute__(self, name)

        # for attributes other than `message` act as a transparent proxy
        record = self.__record
        if name not in ('message', '__dict__'):
            return getattr(record, name)

        # if the message has already been cut
        # -- get it quickly; otherwise cut it
        if hasattr(record, 'message') and not self.__already_cut.pop('thread_safe_flag', True):
            msg_length_limit = self.__msg_length_limit
            if len(record.message) > msg_length_limit:
                # note: here we overwrite the `message` attribute of the
                # record with the abbreviated (cut) form of the message
                # but -- fortunately -- it will not be used by other
                # formatters, because this attribute is re-set during
                # each execution of the `Formatter.format()` method
                # [maybe TODO later: make it more safe and future-proof
                # by avoiding, somehow, mutation of the actual record]
                record.message = record.message[:msg_length_limit] + self.__cut_indicator
        if name == '__dict__':
            return record.__dict__
        else:
            assert name == 'message'
            return record.message

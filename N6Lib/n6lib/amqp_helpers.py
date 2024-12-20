# Copyright (c) 2013-2024 NASK. All rights reserved.

import contextlib
import os
import os.path
import pathlib
import ssl as libssl
import sys
import time
from collections.abc import (
    Callable,
    Generator,
)
from contextvars import ContextVar
from datetime import datetime
from typing import Any

import pika
import pika.credentials
import pika.exceptions

import n6lib.config
import n6lib.const
from n6lib.common_helpers import ascii_str
from n6lib.file_helpers import as_path
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


GUEST_USERNAME = GUEST_PASSWORD = 'guest'

MIN_REQUIRED_PASSWORD_LENGTH = 16
assert MIN_REQUIRED_PASSWORD_LENGTH > len(GUEST_PASSWORD)

PIPELINE_CONFIG_SPEC_PATTERN = '''
    [{pipeline_config_section}]
    ... :: list_of_str
'''

RABBITMQ_CONFIG_SPEC_PATTERN = '''
    [{rabbitmq_config_section}]

    host :: str
    port :: int
    heartbeat_interval :: int

    ssl :: bool   ; always recommended to be true (at least on production systems)

    # Path of CA certificate(s) file:
    ssl_ca_certs = :: str   ; needs to be specified *if* `ssl` is true

    # Path of client certificate file & path of that certificate's private
    # key file, both related to client-certificate-based authentication:
    ssl_certfile = :: str   ; these two are relevant only if `input_ssl` is
    ssl_keyfile = :: str    ; true *and* `password_auth` is false

    # Options related to username-and-password-based authentication:
    password_auth = false :: bool
    username = :: str   ; relevant *only if* `password_auth` is true
    password = :: str   ; relevant *only if* `password_auth` is true
    # ^ Note: if `password_auth` is true and `username` is set to a non-empty
    # value other than guest, `password` needs to be set to a secret password
    # being at least 16 characters long.

    ...
'''

# components (subclasses of `n6datapipeline.base.LegacyQueuedBase`)
# which have the `input_queue` attribute set,
# but they do not need to have the list of `binding_keys`,
# the warning will not be logged for them
PIPELINE_OPTIONAL_COMPONENTS = [
    'dbarchiver',
    'restorer',
    'splunkemitter',
]
# similar list like the `PIPELINE_OPTIONAL_COMPONENTS`, but
# may contain names of groups of components (e.g., 'collectors',
# 'parsers')
PIPELINE_OPTIONAL_GROUPS = [
    'collectors',
    'parsers',
]


class AMQPConnectionParamsError(Exception):
    """Raised by `get_amqp_connection_params_dict_from_args()`..."""


class SimpleAMQPExchangeTool:

    """
    A simple tool to declare, bind and delete AMQP exchanges.

    AMQP broker connection parameters are obtained by calling
    `get_amqp_connection_params_dict()`.
    """

    CONNECTION_ATTEMPTS = 10
    CONNECTION_RETRY_DELAY = 0.5

    def __init__(self, *, rabbitmq_config_section='rabbitmq'):
        self._connection_params_dict = get_amqp_connection_params_dict(
            rabbitmq_config_section=rabbitmq_config_section)
        self._connection = None
        self._channel = None

    def __enter__(self):
        self._connection = self._make_connection()
        self._channel = self._connection.channel()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._connection.close()
        self._connection = None
        self._channel = None

    def declare_exchange(self, exchange, exchange_type, **kwargs):
        self._channel.exchange_declare(exchange=exchange, exchange_type=exchange_type, **kwargs)
        LOGGER.info('Exchange %a has been declared', exchange)

    def bind_exchange_to_exchange(self, exchange, source_exchange, **kwargs):
        self._channel.exchange_bind(destination=exchange, source=source_exchange, **kwargs)
        LOGGER.info('Exchange %a has been bound to source exchange %a',
                    exchange, source_exchange)

    def delete_exchange(self, exchange, **kwargs):
        self._channel.exchange_delete(exchange=exchange, **kwargs)
        LOGGER.info('Exchange %a has been deleted', exchange)

    def _make_connection(self):
        last_exc = None
        try:
            for _ in range(self.CONNECTION_ATTEMPTS):
                parameters = pika.ConnectionParameters(**self._connection_params_dict)
                try:
                    return pika.BlockingConnection(parameters)
                except pika.exceptions.AMQPConnectionError as exc:
                    time.sleep(self.CONNECTION_RETRY_DELAY)
                    last_exc = exc
            assert last_exc is not None
            raise last_exc
        finally:
            # (Breaking the traceback-related reference cycle...)
            del last_exc


def get_pipeline_binding_states(pipeline_group,
                                pipeline_name,
                                pipeline_config_section='pipeline'):
    """
    Get the list of "binding states" for the component, or its group,
    from the pipeline config. Pipeline config for an individual
    component has a priority over group's config.

    Args:
        `pipeline_group`:
            A group which the component is bound to.
        `pipeline_name`:
            Name of the component in the pipeline config format,
            which is, by default, a lowercase component's
            class' name.
        `pipeline_config_section`:
            Name of the pipeline config section, "pipeline"
            by default.

    Returns:
        The list of "binding states" for the component, or None,
        if no config option could be found.
    """
    config_spec = PIPELINE_CONFIG_SPEC_PATTERN.format(
        pipeline_config_section=pipeline_config_section)
    pipeline_conf = n6lib.config.Config.section(config_spec)
    try:
        return pipeline_conf[pipeline_name]
    except KeyError:
        pass
    try:
        return pipeline_conf[pipeline_group]
    except KeyError:
        return None


def get_amqp_connection_params_dict(rabbitmq_config_section='rabbitmq'):
    """
    Prepare AMQP connection parameters (as a dict) based on config.

    Returns:
        A dict that can be used as **kwargs for pika.ConnectionParameters.

    Raises:
        n6lib.config.ConfigError if some config options are invalid,
        wrongly unspecified or over-specified.
    """
    config_spec = RABBITMQ_CONFIG_SPEC_PATTERN.format(
        rabbitmq_config_section=rabbitmq_config_section)
    config = n6lib.config.Config.section(config_spec)
    try:
        return get_amqp_connection_params_dict_from_args(
            host=config['host'],
            port=config['port'],
            heartbeat_interval=config['heartbeat_interval'],

            ssl=config['ssl'],
            ssl_ca_certs=config['ssl_ca_certs'],
            ssl_certfile=config['ssl_certfile'],
            ssl_keyfile=config['ssl_keyfile'],

            password_auth=config['password_auth'],
            username=config['username'],
            password=config['password'])
    except AMQPConnectionParamsError as exc:
        raise n6lib.config.ConfigError(
            f'in section '
            f'{ascii_str(rabbitmq_config_section)}: '
            f'{ascii_str(exc)}'
        ) from exc


def get_amqp_connection_params_dict_from_args(
        host,
        port,

        # (Note: it is planned that in a future version of *n6* all
        # parameters except `host` and `port` will be *keyword-only*
        # ones, so passing any of them as a positional argument should
        # now be considered deprecated!)

        heartbeat_interval=None,  # Note: None means that the server's proposal will be accepted
        ssl=False,

        # Note: in the future, most probably, the following three parameters
        # will be replaced with their current `ssl_*` "aliases" (see below...).
        ca_certs=None,  # (Note: empty str is considered as equivalent to None)
        certfile=None,  # (Note: empty str is considered as equivalent to None)
        keyfile=None,  # (Note: empty str is considered as equivalent to None)

        *,
        password_auth=False,
        username=None,  # (Note: empty str is considered as equivalent to None)
        password=None,  # (Note: empty str is considered as equivalent to None)

        # ---------------------------------------------------------------
        # All parameters declared below are *experimental*, i.e., they may
        # be removed or their semantics may be changed even in minor *n6*
        # versions without any warnings etc.

        # The `ssl_options` argument -- if given -- is expected to be a
        # dict of **kwargs ready to be passed to ssl.wrap_socket(); if
        # it contains 'ca_certs', 'certfile' or 'keyfile' which is not
        # None/empty value, the corresponding `ca_certs`, `certfile` or
        # `keyfile` argument (declared above) as well as its `ssl_*`
        # "alias" arguments (declared below) must be either omitted or
        # set to None/empty value (otherwise TypeError will be raised).
        # Note: in the future, most probably, this parameter will just
        # be removed.
        ssl_options=None,

        # The following three `ssl_*` parameters are "aliases" for the
        # 'ca_certs', 'certfile' and 'keyfile' parameters (respectively)
        # declared above. Their semantics are (respectively) the same.
        # If 'ca_certs', 'certfile' or 'keyfile' is set to a value other
        # than None or an empty value, the corresponding `ssl_*` "alias"
        # must be either omitted or set to None/empty value (otherwise
        # TypeError will be raised). Note: in the future, most probably,
        # these "aliases" will become the canonical way to specify the
        # x.509 CA/certificate/key file paths -- therefore it is a good
        # idea to make use of them (rather than of the alternatives that
        # are declared above).
        ssl_ca_certs=None,  # (Note: empty str is considered as equivalent to None)
        ssl_certfile=None,  # (Note: empty str is considered as equivalent to None)
        ssl_keyfile=None,  # (Note: empty str is considered as equivalent to None)
        # ---------------------------------------------------------------
):
    """
    Prepare AMQP connection parameters (as a dict) based on the given arguments.

    Returns:
        A dict that can be used as **kwargs for pika.ConnectionParameters.

    Raises:
        * TypeError if `username` or `password` is not a str.
        * TypeError if `ssl_options` is neither None nor a dict.
        * TypeError if `ca_certs`/`certfile`/`keyfile` is neither None
          nor empty, *and* the respective "alias" argument, `ssl_ca_certs`
          /`ssl_certfile`/`ssl_keyfile`, is also neither None nor empty.
        * TypeError if `ca_certs`/`certfile`/`keyfile` (or the respective
          "alias" argument, `ssl_ca_certs`/`ssl_certfile`/`ssl_keyfile`)
          is neither None nor empty, *and* the value for the corresponding
          item ('ca_certs'/'certfile'/'keyfile') in the given `ssl_options`
          dict is also neither None nor empty.
        * AMQPConnectionParamsError if some connection parameters are
          wrongly unspecified or over-specified.
    """
    (
        ssl,
        ca_certs,
        certfile,
        keyfile,
        ssl_options,
        password_auth,
        username,
        password,
    ) = _preprocess_args(
        ssl=ssl,
        ca_certs=ca_certs,
        certfile=certfile,
        keyfile=keyfile,
        ssl_options=ssl_options,
        password_auth=password_auth,
        username=username,
        password=password,
        ssl_ca_certs=ssl_ca_certs,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )

    params_dict = dict(
        host=host,
        port=port,
        client_properties=get_n6_default_client_properties_for_amqp_connection(),
        ssl=ssl,
    )

    if ssl:
        _check_and_provide_ssl_stuff(
            params_dict,
            ssl=ssl,
            ca_certs=ca_certs,
            certfile=certfile,
            keyfile=keyfile,
            ssl_options=ssl_options,
            password_auth=password_auth,
        )
    else:
        _log_warning(
            f'{ssl=!a}, so AMQP communication will *not* be '
            f'TLS-secured, even though it always *should be* '
            f'on any production system! (regardless of how '
            f'authentication is performed)',
        )

    if password_auth:
        _check_and_provide_password_auth_stuff(
            params_dict,
            password_auth=password_auth,
            username=username,
            password=password,
        )

    if 'credentials' not in params_dict:
        params_dict['credentials'] = pika.credentials.PlainCredentials(
            GUEST_USERNAME,
            GUEST_PASSWORD,
        )
        _log_warning(
            f'{password_auth=!a}, {ssl=!a}, {certfile=!a} and '
            f'{keyfile=!a}, so *no* real AMQP authentication '
            f'will be performed, even though it always *should '
            f'be* on any production system! (Instead, a *guest* '
            f'pseudo-authentication is to be attempted!)',
        )

    if heartbeat_interval is not None:
        params_dict['heartbeat_interval'] = heartbeat_interval

    return params_dict


# *Warning-logging customization stuff*
#
# Considering that the `get_amqp_connection_params_dict_from_args()`
# function may be used also when *logging* is not (yet) configured,
# we need to be able to customize how that function (and the helper
# functions, defined below...) log/print any warnings.

# This non-public helper is intended to be invoked only by the function
# `get_amqp_connection_params_dict_from_args()` and this-module-local
# helpers invoked by it.
def _log_warning(warning_text: str) -> None:
    func = __log_warning_func_context_var.get(LOGGER.warning)
    func(warning_text)

# (Internal stuff)
__log_warning_func_context_var = ContextVar('_log_warning_func_context_var')

# (Internal stuff)
@contextlib.contextmanager
def __set_log_warning_func_impl(func: Callable[[str], Any]) -> Generator[Callable[[str], Any]]:
    context_token = __log_warning_func_context_var.set(func)
    try:
        yield func
    finally:
        __log_warning_func_context_var.reset(context_token)

# This `get_amqp_connection_params_dict_from_args()` function's public
# attribute, named `set_log_warning_func`, is a function that takes a
# *log-or-print-a-warning* callable and returns a context manager. Use
# it (with the `with ...` Python syntax) to replace -- temporarily and
# locally to the current thread -- all invocations of `LOGGER.warning()`
# made by `_log_warning()` (see above) with invocations of the specified
# callable. The only requirement regarding that callable is that it must
# be able to take a warning text (str) as the sole positional argument.
#
# Example use:
#     def custom_warn(text):
#         print('WARNING:', text, file=sys.stderr)
#     with get_amqp_connection_params_dict_from_args.set_log_warning_func(custom_warn):
#         get_amqp_connection_params_dict_from_args(**some_kwargs)
#
get_amqp_connection_params_dict_from_args.set_log_warning_func = __set_log_warning_func_impl


def _preprocess_args(*,
                     ssl,
                     ca_certs,
                     certfile,
                     keyfile,
                     ssl_options,
                     password_auth,
                     username,
                     password,
                     ssl_ca_certs,
                     ssl_certfile,
                     ssl_keyfile):

    # * Coerce flag arguments to `bool`:

    ssl = bool(ssl)
    password_auth = bool(password_auth)

    # * Resolve CA/cert/key path argument "aliases":

    if ssl_ca_certs:
        if ca_certs:
            raise TypeError(
                f'{ssl_ca_certs=!a} and {ca_certs=!a} '
                f'(only one of them should be specified)',
            )
        ca_certs = ssl_ca_certs
    if ssl_certfile:
        if certfile:
            raise TypeError(
                f'{ssl_certfile=!a} and {certfile=!a} '
                f'(only one of them should be specified)',
            )
        certfile = ssl_certfile
    if ssl_keyfile:
        if keyfile:
            raise TypeError(
                f'{ssl_keyfile=!a} and {keyfile=!a} '
                f'(only one of them should be specified)',
            )
        keyfile = ssl_keyfile

    # * Do simple type checks:

    if ssl_options is not None and not isinstance(ssl_options, dict):
        raise TypeError(
            f'ssl_options must be a dict or None '
            f'(got an instance of {type(ssl_options).__qualname__!a})',
        )

    if username is not None and not isinstance(username, str):
        raise TypeError(
            f'username must be a str or None '
            f'(got an instance of {type(username).__qualname__!a})',
        )

    if password is not None and not isinstance(password, str):
        raise TypeError(
            f'password must be a str or None '
            f'(got an instance of {type(password).__qualname__!a})',
        )

    # * Log warnings if some arguments are to be ignored:

    _warn_on_ignored_ssl_related_args(
        ssl=ssl,
        ca_certs=ca_certs,
        certfile=certfile,
        keyfile=keyfile,
        ssl_options=ssl_options,
    )
    _warn_on_ignored_password_auth_related_args(
        password_auth=password_auth,
        username=username,
        password=password,
    )

    # * Adjust `ssl_options` and `ca_certs`/`certfile`/`keyfile`:

    if ssl_options is None:
        ssl_options = {}
    else:
        ssl_options = ssl_options.copy()

        opt_ca_certs = ssl_options.pop('ca_certs', None)
        if opt_ca_certs:
            if ca_certs:
                raise TypeError(
                    f"{ca_certs=!a} and ssl_options['ca_certs']="
                    f"{opt_ca_certs!a} (only one of them should "
                    f"be specified)",
                )
            ca_certs = opt_ca_certs

        opt_certfile = ssl_options.pop('certfile', None)
        if opt_certfile:
            if certfile:
                raise TypeError(
                    f"{certfile=!a} and ssl_options['certfile']="
                    f"{opt_certfile!a} (only one of them should "
                    f"be specified)",
                )
            certfile = opt_certfile

        opt_keyfile = ssl_options.pop('keyfile', None)
        if opt_keyfile:
            if keyfile:
                raise TypeError(
                    f"{keyfile=!a} and ssl_options['keyfile']="
                    f"{opt_keyfile!a} (only one of them should "
                    f"be specified)",
                )
            keyfile = opt_keyfile

    assert isinstance(ssl_options, dict)
    assert {'ca_certs', 'certfile', 'keyfile'}.isdisjoint(ssl_options)

    ca_certs = as_path(ca_certs) if ca_certs else None
    certfile = as_path(certfile) if certfile else None
    keyfile = as_path(keyfile) if keyfile else None

    assert (isinstance(ca_certs, pathlib.Path) and ca_certs) or ca_certs is None
    assert (isinstance(certfile, pathlib.Path) and certfile) or certfile is None
    assert (isinstance(keyfile, pathlib.Path) and keyfile) or keyfile is None

    # * Adjust `username` and `password`:

    if not username:
        username = None
    if not password:
        password = None

    assert (isinstance(username, str) and username) or username is None
    assert (isinstance(password, str) and password) or password is None

    return (
        ssl,
        ca_certs,
        certfile,
        keyfile,
        ssl_options,
        password_auth,
        username,
        password,
    )


def _warn_on_ignored_ssl_related_args(*,
                                      ssl,
                                      ca_certs,
                                      certfile,
                                      keyfile,
                                      ssl_options):
    if not ssl:
        meaningful_ignored_args = []

        if ca_certs:
            meaningful_ignored_args.append(f'{ca_certs=!a}')
        if certfile:
            meaningful_ignored_args.append(f'{certfile=!a}')
        if keyfile:
            meaningful_ignored_args.append(f'{keyfile=!a}')
        if ssl_options:
            meaningful_ssl_option_keys = [
                key for key, val in ssl_options.items()
                if (val
                    or (key not in {'ca_certs', 'certfile', 'keyfile'}))
            ]
            if meaningful_ssl_option_keys:
                # Note: here we do *not* reveal option values.
                meaningful_ignored_args.append(
                    f'ssl_options=<dict containing keys: '
                    f'{", ".join(map(ascii, meaningful_ssl_option_keys))}>'
                )

        if meaningful_ignored_args:
            _log_warning(
                f'{ssl=!a}, so these argument(s) will be '
                f'ignored: {", ".join(meaningful_ignored_args)}.',
            )


def _warn_on_ignored_password_auth_related_args(*,
                                                password_auth,
                                                username,
                                                password):
    if not password_auth:
        meaningful_ignored_args = []

        if username:
            meaningful_ignored_args.append(f'{username=!a}')
        if password:
            # Note: here we do *not* reveal the password.
            meaningful_ignored_args.append('password=<...hidden...>')

        if meaningful_ignored_args:
            _log_warning(
                f'{password_auth=!a}, so these argument(s) will '
                f'be ignored: {", ".join(meaningful_ignored_args)}.',
            )


def _check_and_provide_ssl_stuff(params_dict,
                                 *,
                                 ssl,
                                 ca_certs,
                                 certfile,
                                 keyfile,
                                 ssl_options,
                                 password_auth):

    assert ssl and params_dict.get('ssl') is ssl

    if not ca_certs:
        raise AMQPConnectionParamsError(f'{ssl=!a} but {ca_certs=!a}')
    ssl_options['ca_certs'] = os.path.expanduser(ca_certs)

    cert_reqs = ssl_options.setdefault('cert_reqs', libssl.CERT_REQUIRED)
    if cert_reqs != libssl.CERT_REQUIRED:
        # XXX: according to the docs of the `ssl` standard Py module,
        #      in this case, i.e. the case of the *client side* of a
        #      connection, the value `CERT_OPTIONAL` is automatically
        #      treated as if it was `CERT_REQUIRED`, so the following
        #      warning message may not be accurate if `CERT_OPTIONAL`
        #      is encountered. But let's keep it as-is for a while
        #      -- because quite soon, hopefully, we will hardcode
        #      `CERT_REQUIRED` anyway (as the only sensible option).
        verb = 'will' if cert_reqs == libssl.CERT_NONE else 'may'
        _log_warning(
            f"{ssl_options['cert_reqs']=!a}, so the AMQP server's "
            f"certificate {verb} *not* be verified, even though "
            f"it always *should be* on any production system!",
        )

    if certfile and keyfile:
        if password_auth:
            _log_warning(
                f'{password_auth=!a}, so the specified client certificate '
                f'({certfile=!a} and {keyfile=!a}) will be ignored, i.e., '
                f'it will *not* be used for AMQP authentication.',
            )
        else:
            ssl_options.update(
                certfile=os.path.expanduser(certfile),
                keyfile=os.path.expanduser(keyfile),
            )
            params_dict['credentials'] = pika.credentials.ExternalCredentials()
    elif certfile or keyfile:
        raise AMQPConnectionParamsError(f'{certfile=!a} but {keyfile=!a}')

    params_dict['ssl_options'] = ssl_options


def _check_and_provide_password_auth_stuff(params_dict,
                                           *,
                                           password_auth,
                                           username,
                                           password):

    assert 'credentials' not in params_dict

    if username in (None, GUEST_USERNAME):
        params_dict['credentials'] = pika.credentials.PlainCredentials(
            GUEST_USERNAME,
            GUEST_PASSWORD,
        )
        _log_warning(
            f'{password_auth=!a} but {username=!a}, so a *guest* '
            f'pseudo-authentication is to be attempted! This means '
            f'that *no* real AMQP authentication will be performed, '
            f'even though it always *should be* on any production '
            f'system! (Note: the password, if any is given, is to '
            f'be ignored now; instead of it, the {GUEST_PASSWORD!a} '
            f'password is to be used!)',
        )
    else:
        if password is None or len(password) < MIN_REQUIRED_PASSWORD_LENGTH:
            raise AMQPConnectionParamsError(
                f'password is missing or too short '
                f'(it is required to consist of at least '
                f'{MIN_REQUIRED_PASSWORD_LENGTH} characters)',
            )
        assert username != GUEST_USERNAME
        assert len(password) >= MIN_REQUIRED_PASSWORD_LENGTH > len(GUEST_PASSWORD)

        params_dict['credentials'] = pika.credentials.PlainCredentials(
            username,
            password,
        )


def get_n6_default_client_properties_for_amqp_connection():
    return {
        'information': (
            'Host: {hostname}, '
            'PID: {pid_str}, '
            'script: {script_name}, '
            'args: {args!a}, '
            'modified: {mtime_str}'.format(
                hostname=ascii_str(n6lib.const.HOSTNAME),
                pid_str=str(os.getpid()),
                script_name=ascii_str(n6lib.const.SCRIPT_BASENAME),
                args=sys.argv[1:],
                mtime_str=_get_script_mtime_str(),
            )
        ),
    }


def _get_script_mtime_str():
    unknown_descr = 'UNKNOWN'
    mtime_str = unknown_descr

    if n6lib.const.SCRIPT_FILENAME is not None:
        try:
            mtime = os.stat(n6lib.const.SCRIPT_FILENAME).st_mtime
        except OSError:
            pass
        else:
            mtime_str = '{}Z'.format(datetime.utcfromtimestamp(mtime).replace(microsecond=0))

    if mtime_str == unknown_descr:
        _log_warning('Could not determine script mtime!')

    return mtime_str

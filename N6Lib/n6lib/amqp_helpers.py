# Copyright (c) 2013-2021 NASK. All rights reserved.

import os
import os.path
import ssl as libssl
import sys
from datetime import datetime

import pika.credentials

import n6lib.const
from n6sdk.encoding_helpers import ascii_str


PIPELINE_CONFIG_SPEC_PATTERN = '''
    [{pipeline_config_section}]
    ... :: list_of_str
'''


RABBITMQ_CONFIG_SPEC_PATTERN = '''
    [{rabbitmq_config_section}]
    host
    port :: int
    heartbeat_interval :: int
    ssl :: bool
    ssl_ca_certs = <to be specified if the `ssl` option is true>
    ssl_certfile = <to be specified if the `ssl` option is true>
    ssl_keyfile = <to be specified if the `ssl` option is true>
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
    from n6lib.config import Config

    config_spec = PIPELINE_CONFIG_SPEC_PATTERN.format(
        pipeline_config_section=pipeline_config_section)
    pipeline_conf = Config.section(config_spec)
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
    Get the AMQP connection parameters (as a dict) from config.

    Returns:
        A dict that can be used as **kwargs for pika.ConnectionParameters.
    """

    # Config is imported here to avoid circular dependency
    from n6lib.config import Config

    config_spec = RABBITMQ_CONFIG_SPEC_PATTERN.format(
            rabbitmq_config_section=rabbitmq_config_section)
    queue_conf = Config.section(config_spec)
    return get_amqp_connection_params_dict_from_args(
        host=queue_conf["host"],
        port=queue_conf["port"],
        heartbeat_interval=queue_conf["heartbeat_interval"],
        ssl=queue_conf["ssl"],
        ca_certs=queue_conf.get("ssl_ca_certs", None),
        certfile=queue_conf.get("ssl_certfile", None),
        keyfile=queue_conf.get("ssl_keyfile", None))


def get_amqp_connection_params_dict_from_args(
        host,
        port,
        heartbeat_interval,
        ssl=False,
        ca_certs=None,
        certfile=None,
        keyfile=None):
    """
    Get the AMQP connection parameters (as a dict) from function arguments.

    Returns:
        A dict that can be used as **kwargs for pika.ConnectionParameters.
    """
    params_dict = dict(
        host=host,
        port=port,
        ssl=ssl,
        ssl_options={},
        heartbeat_interval=heartbeat_interval,
        client_properties=get_n6_default_client_properties_for_amqp_connection(),
    )
    if params_dict['ssl']:
        params_dict['credentials'] = pika.credentials.ExternalCredentials()
        params_dict['ssl_options'].update(
            ca_certs=os.path.expanduser(ca_certs),
            certfile=os.path.expanduser(certfile),
            keyfile=os.path.expanduser(keyfile),
            cert_reqs=libssl.CERT_REQUIRED,
        )
    return params_dict


def get_n6_default_client_properties_for_amqp_connection():
    return {
        'information':
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
            ),
    }


def _get_script_mtime_str():
    mtime_str = 'UNKNOWN'
    if n6lib.const.SCRIPT_FILENAME is not None:
        try:
            mtime = os.stat(n6lib.const.SCRIPT_FILENAME).st_mtime
        except OSError:
            pass
        else:
            mtime_str = '{}Z'.format(datetime.utcfromtimestamp(mtime).replace(microsecond=0))
    return mtime_str

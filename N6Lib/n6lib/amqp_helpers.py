# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import os
import ssl
from datetime import datetime

import pika.credentials
from pika.connection import Connection

import n6lib.const


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
    params_dict = dict(
        host=queue_conf["host"],
        port=queue_conf["port"],
        ssl=queue_conf["ssl"],
        ssl_options={},
        heartbeat_interval=queue_conf['heartbeat_interval'],
    )
    if params_dict['ssl']:
        params_dict['credentials'] = pika.credentials.ExternalCredentials()
        params_dict['ssl_options'].update(
            ca_certs=os.path.expanduser(queue_conf["ssl_ca_certs"]),
            certfile=os.path.expanduser(queue_conf["ssl_certfile"]),
            keyfile=os.path.expanduser(queue_conf["ssl_keyfile"]),
            cert_reqs=ssl.CERT_REQUIRED,
        )
    return params_dict


def pika_connection_client_properties_monkeypatching():

    """
    Monkeypatch `pika.Connection._client_properties` property
    to provide the AMQP server with information
    (in AMQP's 'Client properties') about current host, PID,
    connected script and its last modification date.
    """

    hostname = n6lib.const.HOSTNAME
    pid_str = str(os.getpid())
    script_name = n6lib.const.SCRIPT_BASENAME
    mtime_str = _get_script_mtime_str()

    orig_client_properties = Connection._client_properties
    assert isinstance(orig_client_properties, property)

    @property
    def _patched_client_properties(self):
        content = orig_client_properties.fget(self)
        content['information'] = 'Host: {}, PID: {}, script: {}, modified: {}'.format(
            hostname,
            pid_str,
            script_name,
            mtime_str)
        return content

    Connection._client_properties = _patched_client_properties


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

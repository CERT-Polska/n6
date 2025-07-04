# Copyright (c) 2013-2023 NASK. All rights reserved.

import os.path as osp
import re
import socket
import sys

# for backward-compatibility and/or for convenience, the following
# constants importable from n6sdk.data_spec are also accessible via this
# module:
from n6sdk.data_spec import (
    CATEGORY_ENUMS,
    CONFIDENCE_ENUMS,
    ORIGIN_ENUMS,
    PROTO_ENUMS,
    RESTRICTION_ENUMS,
    STATUS_ENUMS,
)


###############################################
### CR: move globally applicable constants here
###############################################


HOSTNAME = socket.gethostname().split('.', 1)[0]
SCRIPT_FILENAME = (sys.argv[0]
                   if sys.argv and sys.argv[0]
                   else None)
SCRIPT_BASENAME = (osp.basename(SCRIPT_FILENAME).split('.', 1)[0]
                   if SCRIPT_FILENAME is not None
                   else 'UNKNOWN')


ETC_DIR = '/etc/n6'
USER_DIR = osp.expanduser('~/.n6')


# how many hexadecimal digits a normalized
# certificate serial number should have in n6 PKI
CERTIFICATE_SERIAL_NUMBER_HEXDIGIT_NUM = 20


# the name of the administrator group in the Auth DB
ADMINS_SYSTEM_GROUP_NAME = 'admins'


# names of HTTP server's environment variables providing SSL information
# - values of client's certificate subject's items

# SSL_CLIENT_S_DN_O - assumed to be organization id (Apache-specific)
WSGI_SSL_ORG_ID_FIELD = 'SSL_CLIENT_S_DN_O'
# SSL_CLIENT_S_DN_CN - assumed to be user id (Apache-specific)
WSGI_SSL_USER_ID_FIELD = 'SSL_CLIENT_S_DN_CN'


# names of HTTP headers characteristic for preflight requests

HTTP_AC_REQUEST_METHOD_HEADER = 'Access-Control-Request-Method'
HTTP_AC_REQUEST_HEADERS_HEADER = 'Access-Control-Request-Headers'


# possible values of the `raw_type` attribute of collector classes,
# and of the `type` property of messages in the `raw` AMQP exchange
RAW_TYPE_ENUMS = (
    'stream',
    'file',
    'blacklist',
)

# possible values of the `type` item of RecordDicts, and of the
# first segment of routing keys in the `event` AMQP exchange
EVENT_TYPE_ENUMS = (
    'event',
    'hifreq',
    'suppressed',
    'bl',
    'bl-new',
    'bl-update',
    'bl-delist',
    'bl-change',
    'bl-expire',
)


SURICATA_SNORT_CATEGORIES = {
    'bots': {'include': False},
    'cnc': {'include': True, 'rep_id': 1, 'descr': 'botnet controllers', 'score_factor': 3, 'classtype': 'trojan-activity'},
    'dos-attacker': {'include': False},
    'dos-victim': {'include': False},
    'malurl': {'include': True, 'rep_id': 2, 'descr': 'malicious URLs', 'score_factor': 2, 'classtype': 'web-application-activity'},
    'phish': {'include': True, 'rep_id': 3, 'descr': 'phishing campaigns', 'score_factor': 2, 'classtype': 'bad-unknown'},
    'proxy': {'include': True, 'rep_id': 4, 'descr': 'open proxy servers', 'score_factor': 1, 'classtype': 'bad-unknown'},
    'amplifier': {'include': True, 'rep_id': 5, 'descr': 'vulnerable services', 'score_factor': 1, 'classtype': 'denial-of-service'},
    'sandbox-url': {'include': True, 'rep_id': 6, 'descr': 'URLs contacted by malware', 'score_factor': 1, 'classtype': 'misc-attack'},
    'scanning': {'include': False},
    'server-exploit': {'include': False},
    'spam': {'include': True, 'rep_id': 7, 'descr': 'hosts sending spam', 'score_factor': 1, 'classtype': 'bad-unknown'},
    'spam-url': {'include': False},
    'tor': {'include': True, 'rep_id': 8, 'descr': 'TOR nodes', 'score_factor': 1, 'classtype': 'bad-unknown'},
    'vulnerable': {'include': False},
    'other': {'include': True, 'rep_id': 9, 'descr': 'other activities', 'score_factor': 2, 'classtype': 'misc-activity'},
}


# the value used in Event DB to denote lack of `ip`/`dip` (as neither `ip`
# nor `dip` can be NULL; see: `etc/mysql/initdb/1_create_tables.sql`...)
LACK_OF_IPv4_PLACEHOLDER_AS_INT = 0
LACK_OF_IPv4_PLACEHOLDER_AS_STR = '0.0.0.0'

# maximum length of a client organization identifier (related both to
# items of the list being the `client` value in a RecordDict / REST API
# query params dict / REST API result dict, and to the `org_id` value
# in an auth db record / n6 Portal log-in input form).
CLIENT_ORGANIZATION_MAX_LENGTH = 32

# a dict that maps categories to sets of standard normalized values
# of the 'name' event attribute (for categories included in the
# dict, setting a non-standard name causes a warning...
# see: RecordDict.adjust_name()); a value can be, instead of
# a set, a name of another category being a key in the dict
CATEGORY_TO_NORMALIZED_NAME = {
    # please maintain alphabetical order for readability!
    'bots': set([
        'citadel',
        'conficker',
        'feodo',
        'irc-bot',
        'kelihos',
        'mirai',
        'palevo',
        'spyeye',
        'tdss',
        'torpig',
        'virut',
        'zeroaccess',
        'zeus-p2p',
        'zeus',
    ]),
    'cnc': 'bots',   # <- for 'cnc' use the same set as for 'bots'
    #'malurl': set([
    #    ## TODO...
    # ]),
}

# a dict that maps first letters of a lowercased but not fully normalized
# value of the 'name' event attribute -- to sequences of pairs:
# (<compiled regular expression>, <normalized value of the 'name' attr>);
# the 'ELSE' key refers to names that do not start with an ASCII letter
NAME_NORMALIZATION = {
    'a': [],
    'b': [
        (re.compile(r'^b54', re.ASCII), 'citadel'),
    ],
    'c': [],
    'd': [],
    'e': [],
    'f': [],
    'g': [],
    'h': [],
    'i': [
        (re.compile(r'^irc$', re.ASCII), 'irc-bot'),
        (re.compile(r'^irc[\W_]?bot(?:net)?$', re.ASCII), 'irc-bot'),
    ],
    'j': [],
    'k': [],
    'l': [],
    'm': [],
    'n': [],
    'o': [],
    'p': [],
    'q': [],
    'r': [],
    's': [],
    't': [],
    'u': [],
    'v': [],
    'w': [],
    'x': [],
    'y': [],
    'z': [],
    'ELSE': [],
}

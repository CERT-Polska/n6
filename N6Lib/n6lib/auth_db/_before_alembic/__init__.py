# Copyright (c) 2018-2020 NASK. All rights reserved.

MYSQL_ENGINE = 'InnoDB'
MYSQL_CHARSET = 'utf8mb4'
MYSQL_COLLATE = 'utf8mb4_nopad_bin'

CLIENT_CA_PROFILE_NAME = 'client'
SERVICE_CA_PROFILE_NAME = 'service'

REGISTRATION_REQUEST_STATUS_NEW = 'new'
REGISTRATION_REQUEST_STATUS_BEING_PROCESSED = 'being_processed'
REGISTRATION_REQUEST_STATUS_ACCEPTED = 'accepted'
REGISTRATION_REQUEST_STATUS_DISCARDED = 'discarded'
REGISTRATION_REQUEST_STATUSES = {
    REGISTRATION_REQUEST_STATUS_NEW,
    REGISTRATION_REQUEST_STATUS_BEING_PROCESSED,
    REGISTRATION_REQUEST_STATUS_ACCEPTED,
    REGISTRATION_REQUEST_STATUS_DISCARDED,
}

MAX_LEN_OF_ORG_ID = 32
MAX_LEN_OF_CERT_SERIAL_HEX = 20
MAX_LEN_OF_COUNTRY_CODE = 2
MAX_LEN_OF_IP_NETWORK = 18
MAX_LEN_OF_SOURCE_ID = 32

MAX_LEN_OF_OFFICIAL_ACTUAL_NAME = 255
MAX_LEN_OF_OFFICIAL_ADDRESS = 255
MAX_LEN_OF_OFFICIAL_ID_OR_TYPE_LABEL = 100
MAX_LEN_OF_OFFICIAL_LOCATION = 100
MAX_LEN_OF_OFFICIAL_LOCATION_COORDS = 100

MAX_LEN_OF_CA_LABEL = 100
MAX_LEN_OF_DOMAIN_NAME = MAX_LEN_OF_EMAIL = MAX_LEN_OF_GENERIC_SHORT_STRING = 255
MAX_LEN_OF_PASSWORD_HASH = 60
MAX_LEN_OF_SYSTEM_GROUP_NAME = 100
MAX_LEN_OF_URL = 2048

# Copyright (c) 2022 NASK. All rights reserved.

import unittest
from unittest.mock import (
    MagicMock,
    patch,
)

from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.ripe_api_client import RIPEApiClient


#
# Test data
#

#
# ASN part

DEFAULT_ASN__ADMINC_TECHC_ROLE_EXAMPLE = {
    'build_version': 'live.2022.2.1.69',
    'cached': False,
    'data': {
        'authorities': ['ripe'],
        'irr_records': [],
        'query_time': '2000-01-01T00:00:00',
        'records': [[
            {
                'details_link': 'https://stat.ripe.net/AS11111',
                'key': 'aut-num',
                'value': '11111',
            },
            {
                'details_link': None,
                'key': 'as-name',
                'value': 'Example-Cloud_1',
            },
            {
                'details_link': None,
                'key': 'remarks',
                'value': 'Example-Cloud_Network_1',
            },
            {
                'details_link': None,
                'key': 'org',
                'value': 'ORG-EXAMPLE-RIPE',
            },
            {
                'details_link': None,
                'key': 'remarks',
                'value': 'Example Company details: http://as11111.example_domain.com',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS2222222222 accept ANY',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS62222222222 action community .= { 6777:6777 }; '
                         'announce AS-ASSA-EUUE',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/ZXCV-EXMPL-RIPE',
                'key': 'admin-c',
                'value': 'ZXCV-EXMPL-RIPE',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/ASDF-EXMPL-RIPE',
                'key': 'tech-c',
                'value': 'ASDF-EXMPL-RIPE',
            },
            {
                'details_link': None,
                'key': 'status',
                'value': 'ASSIGNED',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/RIPE-BEG-END-MNT',
                'key': 'mnt-by',
                'value': 'RIPE-BEG-END-MNT',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/EXMP-CODE',
                'key': 'mnt-by',
                'value': 'EXMP-CODE',
            },
            {
                'details_link': None,
                'key': 'created',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'last-modified',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'source',
                'value': 'RIPE',
            },
        ]],
        'resource': '11111',
    },
    'data_call_name': 'whois',
    'data_call_status': 'supported - connecting to ursa',
    'messages': [],
    'process_time': 50,
    'query_id': '20220202082341-2a1a5670-d197-4530-bd32-491d312deffb',
    'see_also': [],
    'server_id': 'app134',
    'status': 'ok',
    'status_code': 200,
    'time': '2000-01-01T00:00:00Z',
    'version': '4.1',
}

DEFAULT_ASN__ADMINC_TECHC_PERSON_EXAMPLE = {
    'build_version': 'live.2022.1.19.68',
    'cached': False,
    'data': {
        'authorities': ['ripe'],
        'irr_records': [],
        'query_time': '2022-02-01T09:19:00',
        'records': [[
            {
                'details_link': 'https://stat.ripe.net/AS11111111',
                'key': 'aut-num',
                'value': '11111111',
            },
            {
                'details_link': None,
                'key': 'as-name',
                'value': 'MAGICRETAIL',
            },
            {
                'details_link': None,
                'key': 'org',
                'value': 'ORG-MRS11-RIPE',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS333333333333 accept ANY',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS444444444444 accept ANY',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS555555555555 accept ANY',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS666666666666 accept ANY',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS777777777777 announce AS11111111',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS8888888888 announce AS11111111',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS9999 announce AS11111111',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS99999999999 announce AS11111111',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/XXXX_PERSON-RIPE',
                'key': 'admin-c',
                'value': 'XXXX_PERSON-RIPE',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/XXXX_PERSON-RIPE',
                'key': 'tech-c',
                'value': 'XXXX_PERSON-RIPE',
            },
            {
                'details_link': None,
                'key': 'status',
                'value': 'ASSIGNED',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/RIPE-BEG-END-MNT',
                'key': 'mnt-by',
                'value': 'RIPE-BEG-END-MNT',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/mnt-pl-example1-1',
                'key': 'mnt-by',
                'value': 'mnt-pl-example1-1',
            },
            {
                'details_link': None,
                'key': 'created',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'last-modified',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'source',
                'value': 'RIPE',
            },
        ]],
        'resource': '11111111',
    },
    'data_call_name': 'whois',
    'data_call_status': 'supported - connecting to ursa',
    'messages': [],
    'process_time': 47,
    'query_id': '11111111111111-4444444-11111-4a4a-1234-ababababab01010101',
    'see_also': [],
    'server_id': 'app125',
    'status': 'ok',
    'status_code': 200,
    'time': '2022-02-01T09:19:20.153279',
    'version': '4.1',
}

DEFAULT_ASN__ABUSE_CONTACT_REQUEST = {
    'build_version': 'live.2022.2.1.69',
    'cached': True,
    'data': {
        'abuse_contacts': ['example_contact_email@example_domain.com'],
        'authoritative_rir': 'ripe',
        'earliest_time': '2000-01-01T00:00:00',
        'latest_time': '2000-01-01T00:00:00',
        'parameters': {'resource': '<ASN_OR_IP_NETWORK>'},  # irrelevant
    },
    'data_call_name': 'abuse-contact-finder',
    'data_call_status': 'supported',
    'messages': [],
    'process_time': 1,
    'query_id': '20000101123456-afafafafaf-aa11-aa11-aa11-afafafafafaf',
    'see_also': [],
    'server_id': 'app131',
    'status': 'ok',
    'status_code': 200,
    'time': '2000-01-01T00:00:00.111111',
    'version': '2.0',
}


#
# IP network part

DEFAULT_IP_NETWORK__ADMINC_TECHC_ROLE_EXAMPLE = {
    'build_version': 'live.2022.2.1.69',
    'cached': False,
    'data': {
        'authorities': ['ripe'],
        'irr_records': [],
        'query_time': '2000-01-01T00:00:00',
        'records': [[
            {
                'details_link': 'https://stat.ripe.net/1.1.1.1/24',
                'key': 'aut-num',
                'value': '11111',
            },
            {
                'details_link': None,
                'key': 'as-name',
                'value': 'Example-Cloud_1',
            },
            {
                'details_link': None,
                'key': 'remarks',
                'value': 'Example-Cloud_Network_1',
            },
            {
                'details_link': None,
                'key': 'org',
                'value': 'ORG-EXAMPLE-RIPE',
            },
            {
                'details_link': None,
                'key': 'remarks',
                'value': 'Example Company details: http://1.1.1.1/24.example_domain.com',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS2222222222 accept ANY',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS62222222222 action community .= { 6777:6777 }; '
                         'announce AS-ASSA-EUUE',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/AAAA-EXMPL-RIPE',
                'key': 'admin-c',
                'value': 'AAAA-EXMPL-RIPE',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/BBBB-EXMPL-RIPE',
                'key': 'tech-c',
                'value': 'BBBB-EXMPL-RIPE',
            },
            {
                'details_link': None,
                'key': 'status',
                'value': 'ASSIGNED',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/RIPE-BEG-END-MNT',
                'key': 'mnt-by',
                'value': 'RIPE-BEG-END-MNT',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/EXMP-CODE',
                'key': 'mnt-by',
                'value': 'EXMP-CODE',
            },
            {
                'details_link': None,
                'key': 'created',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'last-modified',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'source',
                'value': 'RIPE',
            },
        ]],
        'resource': '11111',
    },
    'data_call_name': 'whois',
    'data_call_status': 'supported - connecting to ursa',
    'messages': [],
    'process_time': 50,
    'query_id': '20220202082341-2a1a5670-d197-4530-bd32-491d312deffb',
    'see_also': [],
    'server_id': 'app134',
    'status': 'ok',
    'status_code': 200,
    'time': '2000-01-01T00:00:00Z',
    'version': '4.1',
}

DEFAULT_IP_NETWORK__ADMINC_TECHC_PERSON_EXAMPLE = {
    'build_version': 'live.2022.1.19.68',
    'cached': False,
    'data': {
        'authorities': ['ripe'],
        'irr_records': [],
        'query_time': '2022-02-01T09:19:00',
        'records': [[
            {
                'details_link': 'https://stat.ripe.net/AS11111111',
                'key': 'aut-num',
                'value': '11111111',
            },
            {
                'details_link': None,
                'key': 'as-name',
                'value': 'MAGICRETAIL',
            },
            {
                'details_link': None,
                'key': 'org',
                'value': 'ORG-MRS11-RIPE',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS333333333333 accept ANY',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS444444444444 accept ANY',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS555555555555 accept ANY',
            },
            {
                'details_link': None,
                'key': 'import',
                'value': 'from AS666666666666 accept ANY',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS777777777777 announce AS11111111',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS8888888888 announce AS11111111',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS9999 announce AS11111111',
            },
            {
                'details_link': None,
                'key': 'export',
                'value': 'to AS99999999999 announce AS11111111',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/XXXX_PERSON-RIPE',
                'key': 'admin-c',
                'value': 'XXXX_PERSON-RIPE',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/person-role/XXXX_PERSON-RIPE',
                'key': 'tech-c',
                'value': 'XXXX_PERSON-RIPE',
            },
            {
                'details_link': None,
                'key': 'status',
                'value': 'ASSIGNED',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/RIPE-BEG-END-MNT',
                'key': 'mnt-by',
                'value': 'RIPE-BEG-END-MNT',
            },
            {
                'details_link': 'https://rest.db.ripe.net/ripe/mntner/mnt-pl-example1-1',
                'key': 'mnt-by',
                'value': 'mnt-pl-example1-1',
            },
            {
                'details_link': None,
                'key': 'created',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'last-modified',
                'value': '2000-01-01T00:00:00Z',
            },
            {
                'details_link': None,
                'key': 'source',
                'value': 'RIPE',
            },
        ]],
        'resource': '11111111',
    },
    'data_call_name': 'whois',
    'data_call_status': 'supported - connecting to ursa',
    'messages': [],
    'process_time': 47,
    'query_id': '11111111111111-4444444-11111-4a4a-1234-ababababab01010101',
    'see_also': [],
    'server_id': 'app125',
    'status': 'ok',
    'status_code': 200,
    'time': '2022-02-01T09:19:20.153279',
    'version': '4.1',
}

DEFAULT_IP_NETWORK__ABUSE_CONTACT_REQUEST = {
    'build_version': 'live.2022.2.1.69',
    'cached': True,
    'data': {
        'abuse_contacts': ['example_contact_email@example_domain.com'],
        'authoritative_rir': 'ripe',
        'earliest_time': '2000-01-01T00:00:00',
        'latest_time': '2000-01-01T00:00:00',
        'parameters': {'resource': '<ASN_OR_IP_NETWORK>'},  # irrelevant
    },
    'data_call_name': 'abuse-contact-finder',
    'data_call_status': 'supported',
    'messages': [],
    'process_time': 1,
    'query_id': '20000101123456-afafafafaf-aa11-aa11-aa11-afafafafafaf',
    'see_also': [],
    'server_id': 'app131',
    'status': 'ok',
    'status_code': 200,
    'time': '2000-01-01T00:00:00.111111',
    'version': '2.0',
}


#
# ASN - case #1

DEFAULT_ASN__PERSON_URL_1 = 'https://rest.db.ripe.net/ripe/role/ASDF-EXMPL-RIPE.json'
DEFAULT_ASN__ROLE_URL_1 = 'https://rest.db.ripe.net/ripe/role/ZXCV-EXMPL-RIPE.json'
DEFAULT_ASN__PERSON_URL_2 = 'https://rest.db.ripe.net/ripe/person/ASDF-EXMPL-RIPE.json'
DEFAULT_ASN__ROLE_URL_2 = 'https://rest.db.ripe.net/ripe/person/ZXCV-EXMPL-RIPE.json'
DEFAULT_ASN__ROLE_DETAILS_REQUEST_1 = {
    'objects': {
        'object': [{
            'attributes': {
                'attribute': [
                    {
                        'name': 'role',
                        'value': 'XXXX_ROLE',
                    },
                    {
                        'name': 'address',
                        'value': 'Example Company',
                    },
                    {
                        'name': 'address',
                        'value': '0001 Example Street_1',
                    },
                    {
                        'name': 'phone',
                        'value': '+11 111 1111 1111',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/role/ZXCV-EXMPL-RIPE',
                            'type': 'locator',
                        },
                        'name': 'admin-c',
                        'referenced-type': 'role',
                        'value': 'ZXCV-EXMPL-RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/role/ZXCV-EXMPL-RIPE',
                            'type': 'locator',
                        },
                        'name': 'tech-c',
                        'referenced-type': 'role',
                        'value': 'ZXCV-EXMPL-RIPE',
                    },
                    {
                        'name': 'nic-hdl',
                        'value': 'ASDF-EXMPL-RIPE',
                    },
                    {
                        'name': 'remarks',
                        'value': '************* PLEASE NOTE **************',
                    },
                    {
                        'name': 'remarks',
                        'value': '********* EXAMPLE REMARKS HERE *********',
                    },
                    {
                        'name': 'abuse-mailbox',
                        'value': 'example_email@example_domain.com',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/mntner/EXMP-CODE',
                            'type': 'locator',
                        },
                        'name': 'mnt-by',
                        'referenced-type': 'mntner',
                        'value': 'EXMP-CODE',
                    },
                    {
                        'name': 'created',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'name': 'last-modified',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'comment': 'Filtered',
                        'name': 'source',
                        'value': 'RIPE',
                    },
                ],
            },
            'link': {
                'href': 'https://rest.db.ripe.net/ripe/role/ASDF-EXMPL-RIPE',
                'type': 'locator',
            },
            'primary-key': {
                'attribute': [{
                    'name': 'nic-hdl',
                    'value': 'ASDF-EXMPL-RIPE',
                }],
            },
            'source': {'id': 'ripe'},
            'type': 'role',
        }],
    },
    'terms-and-conditions': {
        'href': 'http://www.ripe.net/db/support/db-terms-conditions.pdf',
        'type': 'locator',
    },
    'version': {
        'commit-id': '111a11a',
        'timestamp': '2000-01-01T00:00:00Z',
        'version': '1.102.2',
    },
}

DEFAULT_ASN__ROLE_DETAILS_REQUEST_2 = {
    'objects': {
        'object': [{
            'attributes': {
                'attribute': [
                    {
                        'name': 'role',
                        'value': 'Example Cloud - Example Administration',
                    },
                    {
                        'name': 'address',
                        'value': 'Example Company Name',
                    },
                    {
                        'name': 'address',
                        'value': 'Example Street_2',
                    },
                    {
                        'name': 'address',
                        'value': 'Example City',
                    },
                    {
                        'name': 'address',
                        'value': 'GB',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/person/SOME-PRSN-RIPE',
                            'type': 'locator',
                        },
                        'name': 'admin-c',
                        'referenced-type': 'person',
                        'value': 'SOME-PRSN-RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/role/ASDF-EXMPL-RIPE',
                            'type': 'locator',
                        },
                        'name': 'tech-c',
                        'referenced-type': 'role',
                        'value': 'ASDF-EXMPL-RIPE',
                    },
                    {
                        'name': 'nic-hdl',
                        'value': 'ZXCV-EXMPL-RIPE',
                    },
                    {
                        'name': 'created',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'name': 'last-modified',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'comment': 'Filtered',
                        'name': 'source',
                        'value': 'RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/mntner/EXMP-CODE',
                            'type': 'locator',
                        },
                        'name': 'mnt-by',
                        'referenced-type': 'mntner',
                        'value': 'EXMP-CODE',
                    },
                ],
            },
            'link': {
                'href': 'https://rest.db.ripe.net/ripe/role/ZXCV-EXMPL-RIPE',
                'type': 'locator',
            },
            'primary-key': {
                'attribute': [{
                    'name': 'nic-hdl',
                    'value': 'ZXCV-EXMPL-RIPE',
                }],
            },
            'source': {'id': 'ripe'},
            'type': 'role',
        }],
    },
    'terms-and-conditions': {
        'href': 'http://www.ripe.net/db/support/db-terms-conditions.pdf',
        'type': 'locator',
    },
    'version': {
        'commit-id': '1a1a1a1a1aaa',
        'timestamp': '2000-01-01T00:00:00Z',
        'version': '1.102.2',
    },
}

# The following default requests are `None` because two example urls
# have been created basing on the `person` pattern while we need the
# `role` pattern.
DEFAULT_ASN__ROLE_DETAILS_REQUEST_3 = None
DEFAULT_ASN__ROLE_DETAILS_REQUEST_4 = None


#
# ASN - case #2

DEFAULT_ASN__ABUSE_CONTACT_URL_1 = (
    'https://stat.ripe.net/data/abuse-contact-finder/data.json?resource=as22222')
DEFAULT_ASN__PERSON_URL_3 = 'https://rest.db.ripe.net/ripe/person/XXXX_PERSON-RIPE.json'
DEFAULT_ASN__ROLE_URL_3 = 'https://rest.db.ripe.net/ripe/role/XXXX_PERSON-RIPE.json'
DEFAULT_ASN__PERSON_DETAILS_REQUEST_1 = {
    'objects': {
        'object': [{
            'attributes': {
                'attribute': [
                    {
                        'name': 'person',
                        'value': 'Example Person_1',
                    },
                    {
                        'name': 'address',
                        'value': 'Example',
                    },
                    {
                        'name': 'address',
                        'value': 'Street_1',
                    },
                    {
                        'name': 'phone',
                        'value': '+00 00000000',
                    },
                    {
                        'name': 'nic-hdl',
                        'value': 'XXXX_PERSON-RIPE',
                    },
                    {
                        'name': 'created',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'name': 'last-modified',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'comment': 'Filtered',
                        'name': 'source',
                        'value': 'RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/xxxxx/MNT-Person_Example',
                            'type': 'locator',
                        },
                        'name': 'mnt-by',
                        'referenced-type': 'mntner',
                        'value': 'MNT-Person_Example',
                    },
                ]},
            'link': {
                'href': 'https://rest.db.ripe.net/ripe/person/XXXX_PERSON-RIPE',
                'type': 'locator',
            },
            'primary-key': {
                'attribute': [{
                    'name': 'nic-hdl',
                    'value': 'XXXX_PERSON-RIPE',
                }]
            },
            'source': {'id': 'ripe'},
            'type': 'person',
        }]
    },
    'terms-and-conditions': {
        'href': 'http://www.ripe.net/db/support/db-terms-conditions.pdf',
        'type': 'locator',
    },
    'version': {
        'commit-id': '1a1a1a1aa',
        'timestamp': '2000-01-01T00:00:00Z',
        'version': '1.102.2',
    },
}

# It's `None` because example url#2 has been created basing on the
# `person` pattern while we need the `role` pattern.
DEFAULT_ASN__PERSON_DETAILS_REQUEST_2 = None


#
# IP networks input - case #1

DEFAULT_IP_NETWORK__PERSON_URL_1 = 'https://rest.db.ripe.net/ripe/role/AAAA-EXMPL-RIPE.json'
DEFAULT_IP_NETWORK__ROLE_URL_1 = 'https://rest.db.ripe.net/ripe/role/BBBB-EXMPL-RIPE.json'
DEFAULT_IP_NETWORK__PERSON_URL_2 = 'https://rest.db.ripe.net/ripe/person/AAAA-EXMPL-RIPE.json'
DEFAULT_IP_NETWORK__ROLE_URL_2 = 'https://rest.db.ripe.net/ripe/person/BBBB-EXMPL-RIPE.json'
DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_1 = {
    'objects': {
        'object': [{
            'attributes': {
                'attribute': [
                    {
                        'name': 'role',
                        'value': 'XXXX_ROLE',
                    },
                    {
                        'name': 'address',
                        'value': 'Example Company',
                    },
                    {
                        'name': 'address',
                        'value': '0001 Example Street_1',
                    },
                    {
                        'name': 'phone',
                        'value': '+11 111 1111 1111',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/role/BBBB-EXMPL-RIPE',
                            'type': 'locator'
                        },
                        'name': 'admin-c',
                        'referenced-type': 'role',
                        'value': 'BBBB-EXMPL-RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/role/BBBB-EXMPL-RIPE',
                            'type': 'locator',
                        },
                        'name': 'tech-c',
                        'referenced-type': 'role',
                        'value': 'BBBB-EXMPL-RIPE',
                    },
                    {
                        'name': 'nic-hdl',
                        'value': 'AAAA-EXMPL-RIPE',
                    },
                    {
                        'name': 'remarks',
                        'value': '************* PLEASE NOTE **************',
                    },
                    {
                        'name': 'remarks',
                        'value': '********* EXAMPLE REMARKS HERE *********',
                    },
                    {
                        'name': 'abuse-mailbox',
                        'value': 'example_email@example_domain.com',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/mntner/EXMP-CODE',
                            'type': 'locator',
                        },
                        'name': 'mnt-by',
                        'referenced-type': 'mntner',
                        'value': 'EXMP-CODE',
                    },
                    {
                        'name': 'created',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'name': 'last-modified',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'comment': 'Filtered',
                        'name': 'source',
                        'value': 'RIPE',
                    },
                ],
            },
            'link': {
                'href': 'https://rest.db.ripe.net/ripe/role/AAAA-EXMPL-RIPE',
                'type': 'locator',
            },
            'primary-key': {
                'attribute': [{
                    'name': 'nic-hdl',
                    'value': 'AAAA-EXMPL-RIPE',
                }],
            },
            'source': {'id': 'ripe'},
            'type': 'role',
        }],
    },
    'terms-and-conditions': {
        'href': 'http://www.ripe.net/db/support/db-terms-conditions.pdf',
        'type': 'locator',
    },
    'version': {
        'commit-id': '111a11a',
        'timestamp': '2000-01-01T00:00:00Z',
        'version': '1.102.2',
    },
}

DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_2 = {
    'objects': {
        'object': [{
            'attributes': {
                'attribute': [
                    {
                        'name': 'role',
                        'value': 'Example Cloud - Example Administration',
                    },
                    {
                        'name': 'address',
                        'value': 'Example Company Name',
                    },
                    {
                        'name': 'address',
                        'value': 'Example Street_2',
                    },
                    {
                        'name': 'address',
                        'value': 'Example City',
                    },
                    {
                        'name': 'address',
                        'value': 'GB',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/person/SOME-PRSN-RIPE',
                            'type': 'locator',
                        },
                        'name': 'admin-c',
                        'referenced-type': 'person',
                        'value': 'SOME-PRSN-RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/role/AAAA-EXMPL-RIPE',
                            'type': 'locator',
                        },
                        'name': 'tech-c',
                        'referenced-type': 'role',
                        'value': 'AAAA-EXMPL-RIPE',
                    },
                    {
                        'name': 'nic-hdl',
                        'value': 'BBBB-EXMPL-RIPE',
                    },
                    {
                        'name': 'created',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'name': 'last-modified',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'comment': 'Filtered',
                        'name': 'source',
                        'value': 'RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/mntner/EXMP-CODE',
                            'type': 'locator',
                        },
                        'name': 'mnt-by',
                        'referenced-type': 'mntner',
                        'value': 'EXMP-CODE',
                    },
                ],
            },
            'link': {
                'href': 'https://rest.db.ripe.net/ripe/role/BBBB-EXMPL-RIPE',
                'type': 'locator',
            },
            'primary-key': {
                'attribute': [{
                    'name': 'nic-hdl',
                    'value': 'BBBB-EXMPL-RIPE',
                }],
            },
            'source': {'id': 'ripe'},
            'type': 'role',
        }],
    },
    'terms-and-conditions': {
        'href': 'http://www.ripe.net/db/support/db-terms-conditions.pdf',
        'type': 'locator',
    },
    'version': {
        'commit-id': '1a1a1a1a1aaa',
        'timestamp': '2000-01-01T00:00:00Z',
        'version': '1.102.2',
    },
}

# The following default requests are `None` because two example urls
# have been created basing on the `person` pattern while we need the
# `role` pattern.
DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_3 = None
DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_4 = None


#
# IP networks input - case #2

DEFAULT_IP_NETWORK__ABUSE_CONTACT_URL_1 = (
    'https://stat.ripe.net/data/abuse-contact-finder/data.json?resource=1.1.1.1/24')
DEFAULT_IP_NETWORK__PERSON_URL_3 = 'https://rest.db.ripe.net/ripe/person/XXXX_PERSON-RIPE.json'
DEFAULT_IP_NETWORK__ROLE_URL_3 = 'https://rest.db.ripe.net/ripe/role/XXXX_PERSON-RIPE.json'
DEFAULT_IP_NETWORK__PERSON_DETAILS_REQUEST_1 = {
    'objects': {
        'object': [{
            'attributes': {
                'attribute': [
                    {
                        'name': 'person',
                        'value': 'Example Person_1',
                    },
                    {
                        'name': 'address',
                        'value': 'Example',
                    },
                    {
                        'name': 'address',
                        'value': 'Street_1',
                    },
                    {
                        'name': 'phone',
                        'value': '+00 00000000',
                    },
                    {
                        'name': 'nic-hdl',
                        'value': 'XXXX_PERSON-RIPE',
                    },
                    {
                        'name': 'created',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'name': 'last-modified',
                        'value': '2000-01-01T00:00:00Z',
                    },
                    {
                        'comment': 'Filtered',
                        'name': 'source',
                        'value': 'RIPE',
                    },
                    {
                        'link': {
                            'href': 'https://rest.db.ripe.net/ripe/xxxxx/MNT-Person_Example',
                            'type': 'locator',
                        },
                        'name': 'mnt-by',
                        'referenced-type': 'mntner',
                        'value': 'MNT-Person_Example',
                    },
                ],
            },
            'link': {
                'href': 'https://rest.db.ripe.net/ripe/person/XXXX_PERSON-RIPE',
                'type': 'locator',
            },
            'primary-key': {
                'attribute': [{
                    'name': 'nic-hdl',
                    'value': 'XXXX_PERSON-RIPE',
                }],
            },
            'source': {'id': 'ripe'},
            'type': 'person',
        }],
    },
    'terms-and-conditions': {
        'href': 'http://www.ripe.net/db/support/db-terms-conditions.pdf',
        'type': 'locator',
    },
    'version': {
        'commit-id': '1a1a1a1aa',
        'timestamp': '2000-01-01T00:00:00Z',
        'version': '1.102.2',
    },
}

# It's `None` because example url#2 has been created basing on the
# `role` pattern while we need the `person` pattern.
DEFAULT_IP_NETWORK__PERSON_DETAILS_REQUEST_2 = None


#
# Actual tests
#

@expand
class TestRipeApiClient(unittest.TestCase):

    @foreach(
        # ASN Admin-C/Tech-C Role Example
        param(
            asn_seq=['11111'],
            perform_request_mocked_responses=[
                DEFAULT_ASN__ADMINC_TECHC_ROLE_EXAMPLE,
                DEFAULT_ASN__ABUSE_CONTACT_REQUEST,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_1,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_2,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_3,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_4,
            ],
            asn_and_ip_network_to_unique_details_urls={
                'ASN': {
                    '11111': {
                        DEFAULT_ASN__ROLE_URL_1,
                        DEFAULT_ASN__ROLE_URL_2,
                        DEFAULT_ASN__PERSON_URL_1,
                        DEFAULT_ASN__PERSON_URL_2,
                    },
                },
                'IP Network': {},
            },
            expected_attrs=[
                [
                    ('Data for', '11111'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('role', 'XXXX_ROLE'),
                    ('address', 'Example Company'),
                    ('address', '0001 Example Street_1'),
                    ('phone', '+11 111 1111 1111'),
                    ('admin-c', 'ZXCV-EXMPL-RIPE'),
                    ('tech-c', 'ZXCV-EXMPL-RIPE'),
                    ('nic-hdl', 'ASDF-EXMPL-RIPE'),
                    ('remarks', '************* PLEASE NOTE **************'),
                    ('remarks', '********* EXAMPLE REMARKS HERE *********'),
                    ('abuse-mailbox', 'example_email@example_domain.com'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('', ''),
                    ('role', 'Example Cloud - Example Administration'),
                    ('address', 'Example Company Name'),
                    ('address', 'Example Street_2'),
                    ('address', 'Example City'),
                    ('address', 'GB'),
                    ('admin-c', 'SOME-PRSN-RIPE'),
                    ('tech-c', 'ASDF-EXMPL-RIPE'),
                    ('nic-hdl', 'ZXCV-EXMPL-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('', ''),
                ],
            ],
        ),

        # ASN Admin-C/Tech-C Person Example
        param(
            asn_seq=['22222'],
            perform_request_mocked_responses=[
                DEFAULT_ASN__ADMINC_TECHC_PERSON_EXAMPLE,
                DEFAULT_ASN__ABUSE_CONTACT_REQUEST,
                DEFAULT_ASN__PERSON_DETAILS_REQUEST_1,
                DEFAULT_ASN__PERSON_DETAILS_REQUEST_2,
            ],
            asn_and_ip_network_to_unique_details_urls={
                'ASN': {
                    '22222': {
                        DEFAULT_ASN__PERSON_URL_3,
                        DEFAULT_ASN__ROLE_URL_3,
                    },
                },
                'IP Network': {},
            },
            expected_attrs=[
                [
                    ('Data for', '22222'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('person', 'Example Person_1'),
                    ('address', 'Example'),
                    ('address', 'Street_1'),
                    ('phone', '+00 00000000'),
                    ('nic-hdl', 'XXXX_PERSON-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'MNT-Person_Example'),
                    ('', ''),
                ],
            ],
        ),

        # Two ASNs (case#1 + case#2) -> we expect combined results.
        param(
            asn_seq=['11111', '22222'],
            perform_request_mocked_responses=[
                DEFAULT_ASN__ADMINC_TECHC_ROLE_EXAMPLE,
                DEFAULT_ASN__ADMINC_TECHC_PERSON_EXAMPLE,
                DEFAULT_ASN__ABUSE_CONTACT_REQUEST,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_1,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_2,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_3,
                DEFAULT_ASN__ROLE_DETAILS_REQUEST_4,
                DEFAULT_ASN__ABUSE_CONTACT_REQUEST,
                DEFAULT_ASN__PERSON_DETAILS_REQUEST_1,
                DEFAULT_ASN__PERSON_DETAILS_REQUEST_2,
            ],
            asn_and_ip_network_to_unique_details_urls={
                'ASN': {
                    '11111': {
                        DEFAULT_ASN__ROLE_URL_1,
                        DEFAULT_ASN__ROLE_URL_2,
                        DEFAULT_ASN__PERSON_URL_1,
                        DEFAULT_ASN__PERSON_URL_2,
                    },
                    '22222': {
                        DEFAULT_ASN__PERSON_URL_3,
                        DEFAULT_ASN__ROLE_URL_3,
                    },
                },
                'IP Network': {},
            },
            expected_attrs=[
                [
                    ('Data for', '11111'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('role', 'XXXX_ROLE'),
                    ('address', 'Example Company'),
                    ('address', '0001 Example Street_1'),
                    ('phone', '+11 111 1111 1111'),
                    ('admin-c', 'ZXCV-EXMPL-RIPE'),
                    ('tech-c', 'ZXCV-EXMPL-RIPE'),
                    ('nic-hdl', 'ASDF-EXMPL-RIPE'),
                    ('remarks', '************* PLEASE NOTE **************'),
                    ('remarks', '********* EXAMPLE REMARKS HERE *********'),
                    ('abuse-mailbox', 'example_email@example_domain.com'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('', ''),
                    ('role', 'Example Cloud - Example Administration'),
                    ('address', 'Example Company Name'),
                    ('address', 'Example Street_2'),
                    ('address', 'Example City'),
                    ('address', 'GB'),
                    ('admin-c', 'SOME-PRSN-RIPE'),
                    ('tech-c', 'ASDF-EXMPL-RIPE'),
                    ('nic-hdl', 'ZXCV-EXMPL-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('', ''),
                ],
                [
                    ('Data for', '22222'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('person', 'Example Person_1'),
                    ('address', 'Example'),
                    ('address', 'Street_1'),
                    ('phone', '+00 00000000'),
                    ('nic-hdl', 'XXXX_PERSON-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'MNT-Person_Example'),
                    ('', ''),
                ],
            ],
        ),
    )
    def test_run_asn_input(self,
                           asn_seq,
                           perform_request_mocked_responses,
                           asn_and_ip_network_to_unique_details_urls,
                           expected_attrs):
        with patch(
                "n6lib.ripe_api_client.RIPEApiClient._perform_single_request",
                MagicMock(side_effect=perform_request_mocked_responses)):
            ripe_api_client = RIPEApiClient(asn_seq=asn_seq)
            ripe_api_client._obtain_unique_urls_from_asn_records(
                asn_seq=asn_seq)
            attrs = ripe_api_client._get_attrs_data_from_unique_details_urls()
            self.assertEqual(attrs, expected_attrs)
            self.assertEqual(
                ripe_api_client.asn_ip_network_to_details_urls,
                asn_and_ip_network_to_unique_details_urls,
            )

    @foreach(
        # IP Network Admin-C/Tech-C Role Example
        param(
            ip_network_seq=['1.1.1.1/24'],
            perform_request_mocked_responses=[
                DEFAULT_IP_NETWORK__ADMINC_TECHC_ROLE_EXAMPLE,
                DEFAULT_IP_NETWORK__ABUSE_CONTACT_REQUEST,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_1,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_2,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_3,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_4,
            ],
            asn_and_ip_network_to_unique_details_urls={
                'ASN': {},
                'IP Network': {
                    '1.1.1.1/24': {
                        DEFAULT_IP_NETWORK__ROLE_URL_1,
                        DEFAULT_IP_NETWORK__ROLE_URL_2,
                        DEFAULT_IP_NETWORK__PERSON_URL_1,
                        DEFAULT_IP_NETWORK__PERSON_URL_2,
                    },
                },
            },
            expected_attrs=[
                [
                    ('Data for', '1.1.1.1/24'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('role', 'XXXX_ROLE'),
                    ('address', 'Example Company'),
                    ('address', '0001 Example Street_1'),
                    ('phone', '+11 111 1111 1111'),
                    ('admin-c', 'BBBB-EXMPL-RIPE'),
                    ('tech-c', 'BBBB-EXMPL-RIPE'),
                    ('nic-hdl', 'AAAA-EXMPL-RIPE'),
                    ('remarks', '************* PLEASE NOTE **************'),
                    ('remarks', '********* EXAMPLE REMARKS HERE *********'),
                    ('abuse-mailbox', 'example_email@example_domain.com'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('', ''),
                    ('role', 'Example Cloud - Example Administration'),
                    ('address', 'Example Company Name'),
                    ('address', 'Example Street_2'),
                    ('address', 'Example City'),
                    ('address', 'GB'),
                    ('admin-c', 'SOME-PRSN-RIPE'),
                    ('tech-c', 'AAAA-EXMPL-RIPE'),
                    ('nic-hdl', 'BBBB-EXMPL-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('', ''),
                ],
            ],
        ),

        # IP Network Admin-C/Tech-C Person Example
        param(
            ip_network_seq=['2.2.2.2/24'],
            perform_request_mocked_responses=[
                DEFAULT_ASN__ADMINC_TECHC_PERSON_EXAMPLE,
                DEFAULT_ASN__ABUSE_CONTACT_REQUEST,
                DEFAULT_ASN__PERSON_DETAILS_REQUEST_1,
                DEFAULT_ASN__PERSON_DETAILS_REQUEST_2,
            ],
            asn_and_ip_network_to_unique_details_urls={
                'ASN': {},
                'IP Network': {
                    '2.2.2.2/24': {
                        DEFAULT_ASN__PERSON_URL_3,
                        DEFAULT_ASN__ROLE_URL_3,
                    },
                },
            },
            expected_attrs=[
                [
                    ('Data for', '2.2.2.2/24'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('person', 'Example Person_1'),
                    ('address', 'Example'),
                    ('address', 'Street_1'),
                    ('phone', '+00 00000000'),
                    ('nic-hdl', 'XXXX_PERSON-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'MNT-Person_Example'),
                    ('', ''),
                ],
            ],
        ),

        # Two IP Networks (case#1 + case#2) -> we expect combined results.
        param(
            ip_network_seq=['1.1.1.1/24', '2.2.2.2/24'],
            perform_request_mocked_responses=[
                DEFAULT_IP_NETWORK__ADMINC_TECHC_ROLE_EXAMPLE,
                DEFAULT_IP_NETWORK__ADMINC_TECHC_PERSON_EXAMPLE,
                DEFAULT_IP_NETWORK__ABUSE_CONTACT_REQUEST,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_1,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_2,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_3,
                DEFAULT_IP_NETWORK__ROLE_DETAILS_REQUEST_4,
                DEFAULT_IP_NETWORK__ABUSE_CONTACT_REQUEST,
                DEFAULT_IP_NETWORK__PERSON_DETAILS_REQUEST_1,
                DEFAULT_IP_NETWORK__PERSON_DETAILS_REQUEST_2,
            ],
            asn_and_ip_network_to_unique_details_urls={
                'ASN': {},
                'IP Network': {
                    '1.1.1.1/24': {
                        DEFAULT_IP_NETWORK__ROLE_URL_1,
                        DEFAULT_IP_NETWORK__ROLE_URL_2,
                        DEFAULT_IP_NETWORK__PERSON_URL_1,
                        DEFAULT_IP_NETWORK__PERSON_URL_2,
                    },
                    '2.2.2.2/24': {
                        DEFAULT_IP_NETWORK__PERSON_URL_3,
                        DEFAULT_IP_NETWORK__ROLE_URL_3,
                    },
                },
            },
            expected_attrs=[
                [
                    ('Data for', '1.1.1.1/24'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('role', 'XXXX_ROLE'),
                    ('address', 'Example Company'),
                    ('address', '0001 Example Street_1'),
                    ('phone', '+11 111 1111 1111'),
                    ('admin-c', 'BBBB-EXMPL-RIPE'),
                    ('tech-c', 'BBBB-EXMPL-RIPE'),
                    ('nic-hdl', 'AAAA-EXMPL-RIPE'),
                    ('remarks', '************* PLEASE NOTE **************'),
                    ('remarks', '********* EXAMPLE REMARKS HERE *********'),
                    ('abuse-mailbox', 'example_email@example_domain.com'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('', ''),
                    ('role', 'Example Cloud - Example Administration'),
                    ('address', 'Example Company Name'),
                    ('address', 'Example Street_2'),
                    ('address', 'Example City'),
                    ('address', 'GB'),
                    ('admin-c', 'SOME-PRSN-RIPE'),
                    ('tech-c', 'AAAA-EXMPL-RIPE'),
                    ('nic-hdl', 'BBBB-EXMPL-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'EXMP-CODE'),
                    ('', ''),
                ],
                [
                    ('Data for', '2.2.2.2/24'),
                    ('Abuse Contact Emails',
                     ['example_contact_email@example_domain.com']),
                    ('person', 'Example Person_1'),
                    ('address', 'Example'),
                    ('address', 'Street_1'),
                    ('phone', '+00 00000000'),
                    ('nic-hdl', 'XXXX_PERSON-RIPE'),
                    ('created', '2000-01-01T00:00:00Z'),
                    ('last-modified', '2000-01-01T00:00:00Z'),
                    ('source', 'RIPE'),
                    ('mnt-by', 'MNT-Person_Example'),
                    ('', ''),
                ],
            ],
        ),
    )
    def test_run_ip_network_input(self,
                                  ip_network_seq,
                                  perform_request_mocked_responses,
                                  asn_and_ip_network_to_unique_details_urls,
                                  expected_attrs):
        with patch(
                "n6lib.ripe_api_client.RIPEApiClient._perform_single_request",
                MagicMock(side_effect=perform_request_mocked_responses)):
            ripe_api_client = RIPEApiClient(ip_network_seq=ip_network_seq)
            ripe_api_client._obtain_unique_urls_from_ip_network_records(
                ip_network_seq=ip_network_seq)
            attrs = ripe_api_client._get_attrs_data_from_unique_details_urls()
            self.assertEqual(attrs, expected_attrs)
            self.assertEqual(
                ripe_api_client.asn_ip_network_to_details_urls,
                asn_and_ip_network_to_unique_details_urls,
            )

    @foreach(
        param(
            asn_seq=['111'],
            expected_asn_seq=['111'],
        ).label('Valid ASN'),

        param(
            asn_seq=['111', '222', '333'],
            expected_asn_seq=['111', '222', '333'],
        ).label('Three valid ASN'),

        param(
            asn_seq=['11111111111', '222', '333'],
            expected_error=ValueError,
        ).label('One of provided ASN is not valid (more than 10 digits).'),

        param(
            asn_seq=['this_is_not_ASN', '222', '333'],
            expected_error=ValueError,
        ).label('One of provided ASN is not a number.'),

        param(
            asn_seq=[''],
            expected_error=ValueError,
        ).label('Invalid ASN (empty string)'),
    )
    def test__get_validated_as_numbers(self,
                                       asn_seq,
                                       expected_asn_seq=None,
                                       expected_error=None):
        """
        Note: we test this method by providing selected `asn_seq` args
        to __init__() because that is the way this validation works
        in the Client.
        """
        if expected_error is not None:
            with self.assertRaises(expected_error):
                instance = RIPEApiClient(asn_seq=asn_seq)
        else:
            instance = RIPEApiClient(asn_seq=asn_seq)
            self.assertEqual(instance.asn_seq, expected_asn_seq)

    @foreach(
        param(
            ip_network_seq=['1.1.1.1/24'],
            expected_ip_network_seq=['1.1.1.1/24'],
        ).label('Valid IP Network'),

        param(
            ip_network_seq=['1.1.1.1/24', '2.2.2.2/24', '3.3.3.3/24'],
            expected_ip_network_seq=['1.1.1.1/24', '2.2.2.2/24', '3.3.3.3/24'],
        ).label('Three valid IP Networks'),

        param(
            ip_network_seq=['1111.1.1.1/24'],
            expected_error=ValueError,
        ).label('Invalid IP Network'),

        param(
            ip_network_seq=['1.1.1.1'],
            expected_error=ValueError,
        ).label('Valid IP address but not an IP Network.'),

        param(
            ip_network_seq=[1111],
            expected_error=TypeError,
        ).label('Provided data is not str/bytes-like object'),
    )
    def test__get_validated_ip_networks(self,
                                        ip_network_seq,
                                        expected_ip_network_seq=None,
                                        expected_error=None):
        """
        Note: we test this method by providing selected `ip_network_seq`
        args to __init__() because that is the way this validation works
        in the Client.
        """
        if expected_error is not None:
            with self.assertRaises(expected_error):
                instance = RIPEApiClient(ip_network_seq=ip_network_seq)
        else:
            instance = RIPEApiClient(ip_network_seq=ip_network_seq)
            self.assertEqual(instance.ip_network_seq, expected_ip_network_seq)

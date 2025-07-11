# Copyright (c) 2013-2023 NASK. All rights reserved.

import copy
import datetime
import unittest
from unittest.mock import MagicMock

from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.data_spec import N6DataSpec
from n6lib.datetime_helpers import (
    FixedOffsetTimezone,
)
from n6lib.unit_test_helpers import TestCaseMixin
from n6sdk.exceptions import (
    ParamKeyCleaningError,
    ParamValueCleaningError,
    ResultKeyCleaningError,
    ResultValueCleaningError,
)


@expand
class TestN6DataSpec(TestCaseMixin, unittest.TestCase):

    # constants related to the actual behaviour of N6DataSpec

    PARAM_KEYS = {
        'id', 'rid', 'client', 'ignored',
        'source', 'restriction', 'confidence', 'category',
        'time.min', 'time.max', 'time.until',
        'origin', 'name', 'name.sub', 'target',
        'ip', 'ip.net', 'asn', 'cc',
        'url', 'url.sub', 'url.b64', 'fqdn', 'fqdn.sub',
        'proto', 'sport', 'dport', 'dip',
        'md5', 'sha1', 'sha256',
        'active.min', 'active.max', 'active.until',
        'status', 'replaces',
        'modified.min', 'modified.max', 'modified.until',
        'opt.primary', 'opt.limit',
    }

    RESTRICTED_PARAM_KEYS = {
        'client',
        'ignored',
        'rid',
        'restriction',
        'dip',
        'name.sub',
    }

    ANONYMIZED_PARAM_KEYS = {
        'source',
    }

    UNRESTRICTED_PARAM_KEYS = PARAM_KEYS - (RESTRICTED_PARAM_KEYS | ANONYMIZED_PARAM_KEYS)

    NONCUSTOM_RESULT_KEYS = {
        'id', 'rid', 'client', 'ignored',
        'source', 'restriction', 'confidence', 'category', 'time',
        'origin', 'name', 'target',
        'address', 'url', 'fqdn',
        'proto', 'sport', 'dport', 'dip',
        'md5', 'sha1', 'sha256',
        'expires', 'status', 'replaces', 'until', 'count',
        'modified',
    }

    CUSTOM_RESULT_KEYS = {
        'adip',
        'additional_data',
        'artemis_uuid',
        'alternative_fqdns',
        'count_actual',
        'description',
        'ip_network',
        'min_amplification',
        'request',
        'user_agent',
        'sender',
        'botid',
        'method',
        'channel',
        'intelmq',
        'internal_ip',
        'dataset',
        'first_seen',
        'referer',
        'rt',
        'proxy_type',
        'dns_version',
        'facebook_id',
        'gca_specific',
        'ipmi_version',
        'mac_address',
        'misp_eventdid',  # use of the field is deprecated
        'misp_attr_uuid',
        'misp_event_uuid',
        'snitch_uuid',
        'sysdesc',
        'version',
        'header',
        'detected_since',
        'handshake',
        'cert_length',
        'subject_common_name',
        'visible_databases',
        'url_pattern',
        'urls_matched',
        'username',
        'email',
        'iban',
        'injects',
        'phone',
        'product',
        'registrar',
        'x509fp_sha1',
        'x509issuer',
        'x509subject',
        'action',
        'tags',
        'filename',
        'block',
        'vendor',
        'revision',
        'product_code',
        'device_vendor',
        'device_type',
        'device_model',
        'device_version',
        'device_id',
    }

    RESULT_KEYS = NONCUSTOM_RESULT_KEYS | CUSTOM_RESULT_KEYS

    RESTRICTED_RESULT_KEYS = {
        'client',
        'ignored',
        'rid',
        'until',
        'count',
    } | CUSTOM_RESULT_KEYS - {
        'adip',
        'block',
        'url_pattern',
        'username',
        'email',
        'iban',
        'injects',
        'phone',
        'product',
        'registrar',
        'x509fp_sha1',
        'x509issuer',
        'x509subject',
        'action',
    }

    ANONYMIZED_RESULT_KEYS = {
        'dip',
        'source',
    }

    UNRESTRICTED_RESULT_KEYS = RESULT_KEYS - (RESTRICTED_RESULT_KEYS | ANONYMIZED_RESULT_KEYS)

    assert not RESTRICTED_PARAM_KEYS & ANONYMIZED_PARAM_KEYS
    assert not RESTRICTED_PARAM_KEYS & UNRESTRICTED_PARAM_KEYS
    assert not ANONYMIZED_PARAM_KEYS & UNRESTRICTED_PARAM_KEYS
    assert PARAM_KEYS == (
        RESTRICTED_PARAM_KEYS |
        ANONYMIZED_PARAM_KEYS |
        UNRESTRICTED_PARAM_KEYS)

    assert not NONCUSTOM_RESULT_KEYS & CUSTOM_RESULT_KEYS
    assert RESULT_KEYS == (
        NONCUSTOM_RESULT_KEYS |
        CUSTOM_RESULT_KEYS)
    assert not RESTRICTED_RESULT_KEYS & ANONYMIZED_RESULT_KEYS
    assert not RESTRICTED_RESULT_KEYS & UNRESTRICTED_RESULT_KEYS
    assert not ANONYMIZED_RESULT_KEYS & UNRESTRICTED_RESULT_KEYS
    assert RESULT_KEYS == (
        RESTRICTED_RESULT_KEYS |
        ANONYMIZED_RESULT_KEYS |
        UNRESTRICTED_RESULT_KEYS)


    # example data used in some tests

    raw_param_dict_base = {
        'id': ['0123456789abcdef0123456789abcdef', '123456789ABCDEF0123456789ABCDEF0'],
        'category': ['bots'],
        'source': ['some.source', 'some.other'],
        'confidence': ['high', 'medium'],
        'ip': ['100.101.102.103'],
        'cc': ['PL', 'US'],
        'asn': ['AS80000', '1'],
        'dport': ['1234'],
        'ip.net': ['100.101.102.103/32', '1.2.3.4/7'],
        'time.min': ['2014-04-01 01:07:42+02:00'],
        'active.min': ['2015-05-02T24:00'],
        'url': [u'http://www.ołówek.EXAMPLĘ.com/\udcddπœ\udcffę\udcff³¢ą.py'],
        'url.sub': [('xx' + 682 * u'\udccc')],
        'url.b64': ['aHR0cDovL3d3dy5vxYLDs3dlay5FWEFNUEzEmC5jb20v3c-AxZP_xJnts7_Cs8KixIUucHk='],
        'fqdn': ['www.test.org', u'www.ołówek.EXAMPLĘ.com'],
        'fqdn.sub': ['ołówek'],
        'opt.primary': [''],
    }
    cleaned_param_dict_base = {
        'id': ['0123456789abcdef0123456789abcdef', '123456789abcdef0123456789abcdef0'],
        'category': ['bots'],
        'source': ['some.source', 'some.other'],
        'confidence': ['high', 'medium'],
        'ip': ['100.101.102.103'],
        'cc': ['PL', 'US'],
        'asn': [80000, 1],
        'dport': [1234],
        'ip.net': [('100.101.102.103', 32), ('1.2.3.4', 7)],
        'time.min': [datetime.datetime(2014, 3, 31, 23, 7, 42)],
        'active.min': [datetime.datetime(2015, 5, 3)],
        'url': [u'http://www.ołówek.EXAMPLĘ.com/\udcddπœ\udcffę\udcff³¢ą.py'],
        'url.sub': [u'xx' + 682 * u'\udccc'],
        'url.b64': [b'http://www.o\xc5\x82\xc3\xb3wek.EXAMPL\xc4\x98.com/'
                    b'\xdd\xcf\x80\xc5\x93\xff\xc4\x99\xed\xb3\xbf\xc2\xb3\xc2\xa2\xc4\x85.py'],
        'fqdn': ['www.test.org', 'www.xn--owek-qqa78b.xn--exampl-14a.com'],
        'fqdn.sub': ['xn--owek-qqa78b'],
        'opt.primary': [True],
    }
    request_parameters = {
        # this one -- required:
        'time.min': True,
        # rest -- optional:
        'id': False,
        'category': False,
        'source': False,
        'confidence': False,
        'ip': False,
        'cc': False,
        'asn': False,
        'dport': False,
        'ip.net': False,
        'active.min': False,
        'url': False,
        'fqdn': False,
        'url.sub': False,
        'url.b64': False,
        'fqdn.sub': False,
        'opt.primary': False,
        # not in raw_param_dict_base/cleaned_param_dict_base:
        'rid': False,
        'ignored': False,
        'dip': False,
        'md5': False,
    }
    assert raw_param_dict_base.keys() <= PARAM_KEYS
    assert raw_param_dict_base.keys() == cleaned_param_dict_base.keys()

    raw_result_dict_base = {
        'id': '0123456789abcdef0123456789abcdef',
        'rid': '3456789abcdef0123456789abcdef012',
        'ignored': False,
        'restriction': 'public',
        'source': 'some.source',
        'confidence': 'low',
        'category': 'bots',
        'address': [
            {
                'ip': '100.101.102.103',
                'cc': 'PL',
                'asn': 80000,
            },
            {
                # not a fully valid item -- to be skipped because:
                # * `ip` is equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` (see #8861)
                'ip': '0.0.0.0',
                'cc': 'AB',
            },
            {
                # not a fully valid item -- to be skipped because:
                # * `ip` is missing
                'asn': 123456789,
            },
            {
                # not a fully valid item -- to be skipped because:
                # * `ip` is None
                'ip': None,
                'cc': 'AB',
                'asn': 123456789,
            },
            {
                'ip': '10.0.255.128',
                'cc': 'US',
                'asn': '65535.65535',
            },
            {
                'ip': '123.123.123.123',
                'cc': None,   # <- to be skipped
                'asn': None,  # <- to be skipped
            },
        ],
        'dport': 1234,
        'time': datetime.datetime(
            2014, 4, 1, 1, 7, 42,
            tzinfo=FixedOffsetTimezone(120)),
        'modified': datetime.datetime(
            2014, 3, 31, 23, 23, 23),
        'url': b'http://www.o\xc5\x82\xc3\xb3wek.EXAMPL\xc4\x98.com/\xdd-TRALAL\xc4\x85.html',
        'fqdn': u'www.ołówek.EXAMPLĘ.com'.encode('utf-8'),
        'username': u'ołówek',
        'block': True,
    }
    cleaned_result_dict_base = {
        'id': '0123456789abcdef0123456789abcdef',
        'rid': '3456789abcdef0123456789abcdef012',
        'ignored': False,
        'restriction': 'public',
        'source': 'some.source',
        'confidence': 'low',
        'category': 'bots',
        'address': [
            {
                'ip': '100.101.102.103',
                'cc': 'PL',
                'asn': 80000,
            },
            {
                'ip': '10.0.255.128',
                'cc': 'US',
                'asn': 4294967295,
            },
            {
                'ip': '123.123.123.123',
            },
        ],
        'dport': 1234,
        'time': datetime.datetime(2014, 3, 31, 23, 7, 42),
        'modified': datetime.datetime(2014, 3, 31, 23, 23, 23),
        'url': u'http://www.ołówek.EXAMPLĘ.com/\udcdd-TRALALą.html',
        'fqdn': u'www.xn--owek-qqa78b.xn--exampl-14a.com',
        'username': u'ołówek',
        'block': True,
    }
    restricted_access_cleaned_result_dict_base = {
        k: ('anonymized.source' if k == 'source' else v)
        for k, v in cleaned_result_dict_base.items()
        if k not in ('rid', 'ignored')}

    assert raw_result_dict_base.keys() <= RESULT_KEYS
    assert raw_result_dict_base.keys() == cleaned_result_dict_base.keys()

    anonymized_source_mapping = {
        'forward_mapping': {
            'some.source': 'anonymized.source',
        },
        'reverse_mapping': {
            'anonymized.source': 'some.source',
        },
    }


    def setUp(self):
        self.ds = N6DataSpec()

    def test__all_keys(self):
        self.assertEqual(
            self.ds.all_keys,
            self.PARAM_KEYS | self.RESULT_KEYS)

    def test__all_param_keys(self):
        self.assertEqual(
            self.ds.all_param_keys,
            self.PARAM_KEYS)

    def test__all_result_keys(self):
        self.assertEqual(
            self.ds.all_result_keys,
            self.NONCUSTOM_RESULT_KEYS | self.CUSTOM_RESULT_KEYS)

    def test__anonymized_param_keys(self):
        self.assertEqual(
            self.ds.anonymized_param_keys,
            self.ANONYMIZED_PARAM_KEYS)

    def test__anonymized_result_keys(self):
        self.assertEqual(
            self.ds.anonymized_result_keys,
            self.ANONYMIZED_RESULT_KEYS)

    def test__unrestricted_param_keys(self):
        self.assertEqual(
            self.ds.unrestricted_param_keys,
            self.UNRESTRICTED_PARAM_KEYS)

    def test__unrestricted_result_keys(self):
        self.assertEqual(
            self.ds.unrestricted_result_keys,
            self.UNRESTRICTED_RESULT_KEYS)

    def test__restricted_param_keys(self):
        self.assertEqual(
            self.ds.restricted_param_keys,
            self.RESTRICTED_PARAM_KEYS)

    def test__restricted_result_keys(self):
        self.assertEqual(
            self.ds.restricted_result_keys,
            self.RESTRICTED_RESULT_KEYS)

    @foreach(
        # without `request_parameters`
        param(
            raw=dict(raw_param_dict_base),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(cleaned_param_dict_base),
        ),
        param(
            raw=dict(raw_param_dict_base),
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                # skipped as not in anonymized_source_mapping:
                source=[]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                category=['illegal']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_error=ParamValueCleaningError,
            # (more value-cleaning-specific tests -- in SDK...)
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                category=['illegal']),
            full_access=False,
            res_limits={'request_parameters': None},
            expected_error=ParamValueCleaningError,
            # (more value-cleaning-specific tests -- in SDK...)
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                rid=['3456789ABCDEF0123456789ABCDEF012']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                rid=['3456789abcdef0123456789abcdef012']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                rid=['3456789ABCDEF0123456789ABCDEF012']),
            full_access=False,
            res_limits={'request_parameters': None},
            # not legal for non-full access
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ignored=['']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ignored=[True]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ignored=['no']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ignored=[False]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ignored=['']),
            full_access=False,
            res_limits={'request_parameters': None},
            # not legal for non-full access
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                source=['anonymized.source', 'some.other']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                # not changed (full access => no deanonymization)
                source=['anonymized.source', 'some.other']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                source=['anonymized.source', 'some.other']),
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                # 'anonymized.source' deanonymized, 'some.other' skipped
                source=['some.source']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ip=['0.0.0.1']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ip=['0.0.0.1']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ip=['0.0.0.1']),
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ip=['0.0.0.1'],
                source=[]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                # 'ip' equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` is illegal
                # (see #8861)
                ip=['0.0.0.0']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_error=ParamValueCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                # 'ip' equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` is illegal
                # (see #8861)
                ip=['0.0.0.0']),
            full_access=False,
            res_limits={'request_parameters': None},
            expected_error=ParamValueCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                dip=['0.10.20.30']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                dip=['0.10.20.30']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                # 'dip' equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` is illegal
                # (see #8861)
                dip=['0.0.0.0']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_error=ParamValueCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                dip=['0.10.20.30']),
            full_access=False,
            res_limits={'request_parameters': None},
            # 'dip' is illegal for non-full-access
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                adip=['x.10.20.30']),
            full_access=True,
            res_limits={'request_parameters': None},
            # 'adip' is always illegal as a param
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                adip=['x.10.20.30']),
            full_access=False,
            res_limits={'request_parameters': None},
            # 'adip' is always illegal as a param
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                illegal=['foo']),
            full_access=True,
            res_limits={'request_parameters': None},
            # absolutely illegal key
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                illegal=['foo']),
            full_access=False,
            res_limits={'request_parameters': None},
            # absolutely illegal key
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                name=['foo']),
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                name=['foo']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                name=['foo'],
                source=['anonymized.source', 'some.other']),
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                name=['foo'],
                source=['some.source']),
        ),
        param(
            raw={
                k: v for k, v in raw_param_dict_base.items()
                if k != 'time.min'},
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned={
                k: v for k, v in cleaned_param_dict_base.items()
                if k != 'time.min'},
        ),
        param(
            raw={
                k: v for k, v in raw_param_dict_base.items()
                if k != 'time.min'},
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                {k: v for k, v in cleaned_param_dict_base.items()
                 if k != 'time.min'},
                source=[]),
        ),

        # with `request_parameters`
        param(
            raw=dict(raw_param_dict_base),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(cleaned_param_dict_base),
        ),
        param(
            raw=dict(raw_param_dict_base),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                # skipped as not in anonymized_source_mapping
                source=[]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                category=['illegal']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_error=ParamValueCleaningError,
            # (more value-cleaning-specific tests -- in SDK...)
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                category=['illegal']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            expected_error=ParamValueCleaningError,
            # (more value-cleaning-specific tests -- in SDK...)
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                rid=['3456789ABCDEF0123456789ABCDEF012']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                rid=['3456789abcdef0123456789abcdef012']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                rid=['3456789ABCDEF0123456789ABCDEF012']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # not legal for non-full access
            # (even when in request_parameters)
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ignored=['']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ignored=[True]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ignored=['no']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ignored=[False]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ignored=['no']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # not legal for non-full access
            # (even when in request_parameters)
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                source=['anonymized.source', 'some.other']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                # not changed (full access => no deanonymization)
                source=['anonymized.source', 'some.other']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                source=['anonymized.source', 'some.other']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                # 'anonymized.source' deanonymized, 'some.other' skipped
                source=['some.source']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ip=['0.0.0.1']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ip=['0.0.0.1']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                ip=['0.0.0.1']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                ip=['0.0.0.1'],
                source=[]),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                # 'ip' equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` is illegal
                # (see #8861)
                ip=['0.0.0.0']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_error=ParamValueCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                # 'ip' equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` is illegal
                # (see #8861)
                ip=['0.0.0.0']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            expected_error=ParamValueCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                dip=['0.10.20.30']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_cleaned=dict(
                cleaned_param_dict_base,
                dip=['0.10.20.30']),
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                # 'dip' equal to `n6lib.const.LACK_OF_IPv4_PLACEHOLDER_AS_STR` is illegal
                # (see #8861)
                dip=['0.0.0.0']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            expected_error=ParamValueCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                dip=['0.10.20.30']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # 'dip' is illegal for non-full-access
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                adip=['x.10.20.30']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            # 'adip' is always illegal as a param
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                adip=['x.10.20.30']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # 'adip' is always illegal as a param
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                illegal=['foo']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            # absolutely illegal key
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                illegal=['foo']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # absolutely illegal key
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                name=['foo']),
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            # illegal key -- not declared in request_parameters
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_param_dict_base,
                name=['foo']),
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # illegal key -- not declared in request_parameters
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw={
                k: v for k, v in raw_param_dict_base.items()
                if k != 'time.min'},
            full_access=True,
            res_limits={'request_parameters': request_parameters},
            # missing key -- declared as required in request_parameters
            expected_error=ParamKeyCleaningError,
        ),
        param(
            raw={
                k: v for k, v in raw_param_dict_base.items()
                if k != 'time.min'},
            full_access=False,
            res_limits={'request_parameters': request_parameters},
            # missing key -- declared as required in request_parameters
            expected_error=ParamKeyCleaningError,
        ),

        # parameters added to N6DataSpec immediately after SDK release 0.5.0:
        # * time.until
        param(
            raw={
                (k if k != 'time.min' else 'time.until'): v
                for k, v in raw_param_dict_base.items()},
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned={
                (k if k != 'time.min' else 'time.until'): v
                for k, v in cleaned_param_dict_base.items()},
        ),
        param(
            raw={
                (k if k != 'time.min' else 'time.until'): v
                for k, v in raw_param_dict_base.items()},
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                {(k if k != 'time.min' else 'time.until'): v
                 for k, v in cleaned_param_dict_base.items()},
                source=[]),
        ),
        # * active.until
        param(
            raw={
                (k if k != 'active.min' else 'active.until'): v
                for k, v in raw_param_dict_base.items()},
            full_access=True,
            res_limits={'request_parameters': None},
            expected_cleaned={
                (k if k != 'active.min' else 'active.until'): v
                for k, v in cleaned_param_dict_base.items()},
        ),
        param(
            raw={
                (k if k != 'active.min' else 'active.until'): v
                for k, v in raw_param_dict_base.items()},
            full_access=False,
            res_limits={'request_parameters': None},
            expected_cleaned=dict(
                {(k if k != 'active.min' else 'active.until'): v
                 for k, v in cleaned_param_dict_base.items()},
                source=[]),
        ),
    )
    def test__clean_param_dict(self, raw, full_access, res_limits,
                               expected_cleaned=None, expected_error=None):
        deep_copy_of_raw = copy.deepcopy(raw)
        auth_api = MagicMock(**{'get_anonymized_source_mapping.return_value':
                                self.anonymized_source_mapping})
        if expected_error is None:
            assert expected_cleaned is not None
            actual_cleaned = self.ds.clean_param_dict(
                raw,
                auth_api=auth_api,
                full_access=full_access,
                res_limits=res_limits)
            self.assertEqual(actual_cleaned, expected_cleaned)
        else:
            assert expected_cleaned is None
            with self.assertRaises(expected_error):
                self.ds.clean_param_dict(
                    raw,
                    auth_api=auth_api,
                    full_access=full_access,
                    res_limits=res_limits)
        # ensure that the given dict has not been modified
        self.assertEqualIncludingTypes(deep_copy_of_raw, raw)

    ### maybe TODO: more comprehensive N6DataSpec.clean_param_dict() tests...

    @foreach(
        param(
            raw=dict(raw_result_dict_base),
            full_access=True,
            expected_cleaned=dict(cleaned_result_dict_base),
        ),
        param(
            raw=dict(raw_result_dict_base),
            full_access=False,
            expected_cleaned=dict(restricted_access_cleaned_result_dict_base),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                client=['foo', 'bar']),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                client=['bar', 'foo']),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                client=['foo', 'bar']),
            full_access=False,
            expected_cleaned=dict(restricted_access_cleaned_result_dict_base),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                source='some.other'),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                source='some.other'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                source='some.other'),
            full_access=False,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # anonymized using the default value
                source='hidden.unknown'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                category='illegal'),
            full_access=True,
            expected_error=ResultValueCleaningError,
            # (more value-cleaning-specific tests -- in SDK...)
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                category='illegal'),
            full_access=False,
            expected_error=ResultValueCleaningError,
            # (more value-cleaning-specific tests -- in SDK...)
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                dip='0.10.20.30'),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                dip='0.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                dip='0.10.20.30'),
            full_access=False,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # adip being dip anonymized automatically
                adip='x.x.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                # given adip
                adip='x.10.20.30'),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                # the same given adip
                adip='x.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                # given adip
                adip='x.10.20.30'),
            full_access=False,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # the same given adip
                adip='x.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                # given dip + adip
                dip='0.10.20.30',
                adip='x.10.20.30'),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                # the same given dip + adip
                dip='0.10.20.30',
                adip='x.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                # given dip + adip
                dip='0.10.20.30',
                adip='x.10.20.30'),
            full_access=False,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # no dip, the same given adip
                adip='x.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                dip='0.10.20.30'),
            full_access=False,
            dip_anonymization_disabled_source_ids=frozenset(['some.other']),
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # adip being dip anonymized automatically
                # (anonymization disabled for some other source, not 'some.source')
                adip='x.x.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                dip='0.10.20.30'),
            full_access=False,
            dip_anonymization_disabled_source_ids=frozenset(['some.source']),
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # dip *not* anonymized
                # (anonymization disabled for 'some.source')
                dip='0.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                # given adip
                adip='x.10.20.30'),
            full_access=False,
            dip_anonymization_disabled_source_ids=frozenset(['some.source']),
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # the same given adip
                adip='x.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                # given dip + adip
                dip='0.10.20.30',
                adip='x.10.20.30'),
            full_access=False,
            dip_anonymization_disabled_source_ids=frozenset(['some.source', 'some.other']),
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                # the same given (*not* anonymized) dip + adip
                # (anonymization disabled -- among others -- for 'some.source')
                dip='0.10.20.30',
                adip='x.10.20.30'),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                illegal='foo'),  # illegal key
            full_access=True,
            expected_error=ResultKeyCleaningError,
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                illegal='foo'),  # illegal key
            full_access=False,
            expected_error=ResultKeyCleaningError,
        ),
        param(
            raw={
                # no 'id' (which is one of the required keys)
                k: v for k, v in raw_result_dict_base.items()
                if k != 'id'},
            full_access=True,
            expected_error=ResultKeyCleaningError,
        ),
        param(
            raw={
                # no 'id' (which is one of the required keys)
                k: v for k, v in raw_result_dict_base.items()
                if k != 'id'},
            full_access=False,
            expected_error=ResultKeyCleaningError,
        ),
        param(
            raw={
                # no 'rid' (which is one of the required keys)
                k: v for k, v in raw_result_dict_base.items()
                if k != 'rid'},
            full_access=True,
            expected_error=ResultKeyCleaningError,
        ),
        param(
            raw={
                # no 'rid' (which is one of the required keys)
                k: v for k, v in raw_result_dict_base.items()
                if k != 'rid'},
            full_access=False,
            expected_error=ResultKeyCleaningError,
        ),

        # `opt_primary` and 'enriched'...
        param(
            raw=dict(raw_result_dict_base),
            full_access=True,
            opt_primary=True,
            expected_cleaned=None,
        ),
        param(
            raw=dict(raw_result_dict_base),
            full_access=False,
            opt_primary=True,
            expected_cleaned=None,
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {})),
            full_access=True,
            opt_primary=True,
            expected_cleaned=dict(cleaned_result_dict_base),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {})),
            full_access=False,
            opt_primary=True,
            expected_cleaned=dict(restricted_access_cleaned_result_dict_base),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=(['fqdn'], {})),
            full_access=True,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in cleaned_result_dict_base.items()
                if k != 'fqdn'},
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=(['fqdn'], {})),
            full_access=False,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in restricted_access_cleaned_result_dict_base.items()
                if k != 'fqdn'},
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'fqdn'},
                enriched=(['fqdn'], {})),  # 'fqdn' non-existent
            full_access=True,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in cleaned_result_dict_base.items()
                if k != 'fqdn'},
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'fqdn'},
                enriched=(['fqdn'], {})),  # 'fqdn' non-existent
            full_access=False,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in restricted_access_cleaned_result_dict_base.items()
                if k != 'fqdn'},
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {
                    '100.101.102.103': ['cc'],
                })),
            full_access=True,
            opt_primary=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                address=[
                    {
                        'ip': '100.101.102.103',
                        'asn': 80000,
                    },
                    {
                        'ip': '10.0.255.128',
                        'cc': 'US',
                        'asn': 4294967295,
                    },
                    {
                        'ip': '123.123.123.123',
                    },
                ]),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {
                    '100.101.102.103': ['cc'],
                })),
            full_access=False,
            opt_primary=True,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                address=[
                    {
                        'ip': '100.101.102.103',
                        'asn': 80000,
                    },
                    {
                        'ip': '10.0.255.128',
                        'cc': 'US',
                        'asn': 4294967295,
                    },
                    {
                        'ip': '123.123.123.123',
                    },
                ]),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {
                    '100.101.102.103': ['cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                })),
            full_access=True,
            opt_primary=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                address=[
                    {'ip': '100.101.102.103'},
                    {'ip': '123.123.123.123'},
                ]),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {
                    '100.101.102.103': ['cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                })),
            full_access=False,
            opt_primary=True,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                address=[
                    {'ip': '100.101.102.103'},
                    {'ip': '123.123.123.123'},
                ]),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                address=[
                    {
                        'ip': '100.101.102.103',
                        'cc': 'PL',
                    },
                    {
                        'ip': '10.0.255.128',
                        'asn': '65535.65535',
                    },
                ],
                enriched=([], {
                    '100.101.102.103': ['cc', 'asn'],     # 'asn' non-existent
                    '10.0.255.128': ['ip', 'cc', 'asn'],  # 'cc' non-existent
                })),
            full_access=True,
            opt_primary=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                address=[{'ip': '100.101.102.103'}]),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                address=[
                    {
                        'ip': '100.101.102.103',
                        'cc': 'PL',
                    },
                    {
                        'ip': '10.0.255.128',
                        'asn': '65535.65535',
                    },
                ],
                enriched=([], {
                    '100.101.102.103': ['cc', 'asn'],     # 'asn' non-existent
                    '10.0.255.128': ['ip', 'cc', 'asn'],  # 'cc' non-existent
                    '1.2.8.9': ['ip'],                    # '1.2.8.9' non-existent
                })),
            full_access=False,
            opt_primary=True,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                address=[{'ip': '100.101.102.103'}]),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {
                    '100.101.102.103': ['ip', 'cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                    '1.2.8.9': ['ip'],                    # '1.2.8.9' non-existent
                    '123.123.123.123': ['ip'],
                })),
            full_access=True,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in cleaned_result_dict_base.items()
                if k != 'address'},
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=([], {
                    '100.101.102.103': ['ip', 'cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                    '123.123.123.123': ['ip'],
                })),
            full_access=False,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in restricted_access_cleaned_result_dict_base.items()
                if k != 'address'},
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=(['fqdn'], {
                    '100.101.102.103': ['ip', 'cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                    '123.123.123.123': ['ip'],
                })),
            full_access=True,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in cleaned_result_dict_base.items()
                if k not in ('fqdn', 'address')},
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=(['fqdn'], {
                    '100.101.102.103': ['ip', 'cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                    '123.123.123.123': ['ip'],
                })),
            full_access=False,
            opt_primary=True,
            expected_cleaned={
                k: v for k, v in restricted_access_cleaned_result_dict_base.items()
                if k not in ('fqdn', 'address')},
        ),

        # 'enriched' *without* `opt_primary`
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=(['fqdn'], {
                    '100.101.102.103': ['ip', 'cc', 'asn'],
                    '123.123.123.123': ['ip'],
                })),
            full_access=True,
            opt_primary=False,
            expected_cleaned=dict(cleaned_result_dict_base),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                enriched=(['fqdn'], {
                    '100.101.102.103': ['ip', 'cc', 'asn'],
                    '10.0.255.128': ['ip', 'cc', 'asn'],
                })),
            full_access=False,
            opt_primary=False,
            expected_cleaned=dict(restricted_access_cleaned_result_dict_base),
        ),

        # not a fully valid raw result dict: no 'address', but 'ip' or 'asn' or 'cc' present...
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'address'},
                ip='1.2.3.4',
                asn=123,
                cc='PL'),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                address=[{
                    'ip': '1.2.3.4',
                    'asn': 123,
                    'cc': 'PL',
                }]),
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'address'},
                ip='1.2.3.4',
                asn=None,
                cc='PL'),
            full_access=False,
            expected_cleaned=dict(
                restricted_access_cleaned_result_dict_base,
                address=[{
                    'ip': '1.2.3.4',
                    'cc': 'PL',
                }]),
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'address'},
                ip=None),
            full_access=True,
            expected_cleaned={
                # `ip` is missing or None => no `address`
                k: v for k, v in cleaned_result_dict_base.items()
                if k != 'address'},
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'address'},
                ip=None,
                cc='PL'),
            full_access=False,
            expected_cleaned={
                # `ip` is missing or None => no `address`
                k: v for k, v in restricted_access_cleaned_result_dict_base.items()
                if k != 'address'},
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'address'},
                asn=123),
            full_access=True,
            expected_cleaned={
                # `ip` is missing or None => no `address`
                k: v for k, v in cleaned_result_dict_base.items()
                if k != 'address'},
        ),
        param(
            raw=dict(
                {k: v for k, v in raw_result_dict_base.items()
                 if k != 'address'},
                asn=123,
                cc='PL'),
            full_access=False,
            expected_cleaned={
                # `ip` is missing or None => no `address`
                k: v for k, v in restricted_access_cleaned_result_dict_base.items()
                if k != 'address'},
        ),

        # 'urls_matched'
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched={
                    'o1': [u'http://zażółć.gęślą.jaźń'.encode('utf-8'), b'ftp://\xdd'],
                    'o2': [10000 * u'xą'],
                }),
            full_access=True,
            expected_cleaned=dict(
                cleaned_result_dict_base,
                urls_matched={
                    'o1': [u'ftp://\udcdd', u'http://zażółć.gęślą.jaźń'],
                    'o2': [10000 * u'xą'],
                }),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched={
                    'o1': [u'http://zażółć.gęślą.jaźń'.encode('utf-8'), b'ftp://\xdd'],
                    'o2': [10000 * u'xą'],
                }),
            full_access=False,
            expected_cleaned=dict(restricted_access_cleaned_result_dict_base),
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched={
                    'o1': [123, 42],
                }),
            full_access=True,
            expected_error=ResultValueCleaningError,
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched={
                    'o2': 10000 * u'xą',
                }),
            full_access=True,
            expected_error=ResultValueCleaningError,
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched={
                    33 * 'o': [10000 * u'xą'],
                }),
            full_access=True,
            expected_error=ResultValueCleaningError,
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched={
                    None: [10000 * u'xą'],
                }),
            full_access=True,
            expected_error=ResultValueCleaningError,
        ),
        param(
            raw=dict(
                raw_result_dict_base,
                urls_matched=[10000 * u'xą']),
            full_access=True,
            expected_error=ResultValueCleaningError,
        ),
    )
    def test__clean_result_dict(self, raw, full_access,
                                opt_primary=False,
                                dip_anonymization_disabled_source_ids=frozenset(),
                                expected_cleaned=None, expected_error=None):
        deep_copy_of_raw = copy.deepcopy(raw)
        auth_api = MagicMock(**{
            'get_anonymized_source_mapping.return_value':
                self.anonymized_source_mapping,
            'get_dip_anonymization_disabled_source_ids.return_value':
                dip_anonymization_disabled_source_ids})
        if expected_error is None:
            actual_cleaned = self.ds.clean_result_dict(
                raw,
                auth_api=auth_api,
                full_access=full_access,
                opt_primary=opt_primary)
            self.assertEqual(actual_cleaned, expected_cleaned)
        else:
            assert expected_cleaned is None
            with self.assertRaises(expected_error):
                self.ds.clean_result_dict(
                    raw,
                    auth_api=auth_api,
                    full_access=full_access,
                    opt_primary=opt_primary)
        # ensure that the given dict has not been modified
        self.assertEqualIncludingTypes(deep_copy_of_raw, raw)

    ### maybe TODO: more comprehensive N6DataSpec.clean_result_dict() tests...

    ### maybe TODO later: tests of other methods...
    #def test__...
    #def test__...

    # [note that param_field_specs(), result_field_specs() and
    #  filter_by_which() are tested *indirectly* with
    #  test__{anonymized,unrestricted}_{param,result}_keys()]

    ### will become unnecessary after switching to the new DB schema:
    ## maybe TODO later:
    #def test__generate_sqlalchemy_columns...
    # See: n6lib.tests.test_db_events.Test_n6NormalizedData.test_class_attrs()

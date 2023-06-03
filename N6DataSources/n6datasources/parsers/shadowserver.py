# Copyright (c) 2019-2023 NASK. All rights reserved.

"""
`shadowserver.*` parsers:

* `shadowserver.adb`
* `shadowserver.afp`
* `shadowserver.amqp`
* `shadowserver.ard`
* `shadowserver.chargen`
* `shadowserver.cisco-smart-install`
* `shadowserver.coap`
* `shadowserver.compromised-website`
* `shadowserver.cwmp`
* `shadowserver.darknet`
* `shadowserver.db2`
* `shadowserver.dvr-dhcpdiscover`
* `shadowserver.elasticsearch`
* `shadowserver.exchange`
* `shadowserver.ftp`
* `shadowserver.hadoop`
* `shadowserver.http`
* `shadowserver.ics`
* `shadowserver.ipmi`
* `shadowserver.ipp`
* `shadowserver.isakmp`
* `shadowserver.ldap-tcp`
* `shadowserver.ldap`
* `shadowserver.mdns`
* `shadowserver.memcached`
* `shadowserver.modbus`
* `shadowserver.mongodb`
* `shadowserver.mqtt`
* `shadowserver.mssql`
* `shadowserver.natpmp`
* `shadowserver.netbios`
* `shadowserver.netis`
* `shadowserver.ntp-monitor`
* `shadowserver.ntp-version`
* `shadowserver.open-resolver`
* `shadowserver.portmapper`
* `shadowserver.qotd`
* `shadowserver.radmin`
* `shadowserver.rdp`
* `shadowserver.rdpeudp`
* `shadowserver.redis`
* `shadowserver.rsync`
* `shadowserver.sandbox-url`
* `shadowserver.sinkhole-http`
* `shadowserver.sinkhole`
* `shadowserver.smb`
* `shadowserver.smtp`
* `shadowserver.snmp`
* `shadowserver.ssdp`
* `shadowserver.ssl-freak`
* `shadowserver.ssl-poodle`
* `shadowserver.telnet`
* `shadowserver.tftp`
* `shadowserver.ubiquiti`
* `shadowserver.vnc`
* `shadowserver.xdmcp`
"""

import csv
import datetime
from collections.abc import MutableMapping

from n6datasources.parsers.base import (
    BaseParser,
    BlackListParser,
    add_parser_entry_point_functions,
)
from n6lib.datetime_helpers import parse_iso_datetime_to_utc
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class _ShadowserverAddressFieldsMixin(object):

    @staticmethod
    def _handle_address_field(parsed, address_mapping, row):
        if isinstance(address_mapping, int) or isinstance(address_mapping, str):
            ip = row[address_mapping]
            if ip:
                parsed['address'] = {'ip': ip}
        elif isinstance(address_mapping, MutableMapping):
            parsed['address'] = {address_field: row[key] for
                                 address_field, key in address_mapping.items()}
        else:
            raise ValueError("Invalid type of mapping for the `address` field.")


class _BaseShadowserverParser(_ShadowserverAddressFieldsMixin, BaseParser):
    """
    Abstract class parsers.

    `parse()` method uses dictionary `n6_field_to_data_key_mapping`
    to translate field names contained in data from collector
    to n6 field names.

    `n6_field_to_data_key_mapping` - a dictionary of field names
    {n6_key: data_key} used by `parse()` must be implemented
    in each inheriting parser.
    If 'time' is to be mapped to `data['properties.timestamp']`,
    do not include 'time' key in `n6_field_to_data_key_mapping`.

    *Important*: an "address" field is a special field, containing
    other linked fields: "ip", "asn" and "cc", where the "ip"
    field is mandatory. If an "address" field maps to a single
    label - it is assigned as parsed['address'] = {'ip': value}.
    Otherwise, it should be mapped to a dict, containing mapping
    to all keys, that should be assigned to "address" field, e.g.:
    'address': {'ip': value1, 'asn': value2, 'cc': value3}

    This class can be easily used
    if the data is to be parsed in simple way,
    i.e.: `parsed['n6_key'] = row['source_key']`.
    If at least one field must be parsed
    non-standard way (e.g. parsed['proto'] = 'tcp'),
    extend `parse()` method or use standard inheriting
    from BaseParser and implement your own `parse()` method.
    """

    n6_field_to_data_key_mapping = NotImplemented
    delimiter = ','
    quotechar = '"'

    def parse(self, data):
        rows = csv.DictReader(
            data['csv_raw_rows'],
            delimiter=self.delimiter,
            quotechar=self.quotechar,
        )
        for row in rows:
            with self.new_record_dict(data) as parsed:
                for n6_field, data_field in self.n6_field_to_data_key_mapping.items():
                    if n6_field == 'address':
                        self._handle_address_field(parsed, data_field, row)
                    else:
                        value = row.get(data_field)
                        if value:
                            parsed[n6_field] = value
                if 'time' not in self.n6_field_to_data_key_mapping:
                    parsed['time'] = data.get('properties.timestamp')
                yield parsed


class ShadowserverFtp202204Parser(BaseParser):
    """
    Due to a different parsing logic, this parser does not inherit from
    the `ShadowserverBasicParserBaseClass`.
    """

    default_binding_key = 'shadowserver.ftp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ftp, clear text pass',
    }

    delimiter = ','
    quotechar = '"'

    def parse(self, data):
        rows = csv.DictReader(
            data['csv_raw_rows'],
            delimiter=self.delimiter,
            quotechar=self.quotechar,
        )
        for row in rows:
            if not row['handshake']:
                with self.new_record_dict(data) as parsed:
                    parsed['time'] = row['timestamp']
                    parsed['address'] = {'ip': row['ip']}
                    parsed['dport'] = row['port']
                    parsed['proto'] = row['protocol']
                    parsed['device_vendor'] = row['device_vendor']
                    parsed['device_type'] = row['device_type']
                    parsed['device_model'] = row['device_model']
                    parsed['device_version'] = row['device_version']
                    yield parsed


class ShadowserverCompromisedWebsite201412Parser(BlackListParser):

    default_binding_key = 'shadowserver.compromised-website.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'low',
    }

    EXPIRES_DAYS = 3

    delimiter = ','
    quotechar = '"'

    def parse(self, data):
        rows = csv.DictReader(
            data['csv_raw_rows'],
            delimiter=self.delimiter,
            quotechar=self.quotechar,
        )
        for row in rows:
            with self.new_record_dict(data) as parsed:
                parsed['time'] = row['timestamp']
                parsed['expires'] = parse_iso_datetime_to_utc(
                        data['properties.timestamp']) + datetime.timedelta(days=self.EXPIRES_DAYS)
                if row['ip']:
                    parsed['address'] = {'ip': row['ip']}
                if row['port']:
                    parsed['dport'] = row['port']
                if row['url']:
                    parsed['request'] = row['url']
                if row['http_host']:
                    parsed['fqdn'] = row['http_host']
                if row['category'] == 'cnc':
                    parsed['category'] = 'cnc'
                elif row['category'] == 'ddos':
                    parsed['category'] = 'dos-attacker'
                elif row['category'] == 'malwarehosting':
                    parsed['category'] = 'malurl'
                elif row['category'] == 'phishing':
                    parsed['category'] = 'phish'
                elif row['category'] == 'spam':
                    parsed['category'] = 'spam'
                else:
                    parsed['category'] = 'other'
                if row['tag']:
                    parsed['name'] = row['tag']
                if row['detected_since']:
                    parsed['detected_since'] = row['detected_since']
                yield parsed

class ShadowserverIpmi201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ipmi.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ipmi',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'ipmi_version': 'ipmi_version',
    }


class ShadowserverChargen201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.chargen.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'chargen',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverNetbios201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.netbios.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'netbios',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'proto': 'protocol',
        'mac_address': 'mac_address',
        'dport': 'port',
    }


class ShadowserverNetis201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.netis.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'netis-router',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverNtpVersion201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ntp-version.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ntp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverSmb201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.smb.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'smb',
        'proto': 'tcp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': {'ip': 'ip'},
        'dport': 'port',
    }


class ShadowserverSnmp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.snmp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'snmp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'sysdesc': 'sysdesc',
        'version': 'version',
    }


class ShadowserverQotd201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.qotd.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'qotd',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverSsdp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ssdp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ssdp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'header': 'header',
    }


class ShadowserverSslPoodle201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ssl-poodle.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ssl-poodle',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'handshake': 'handshake',
        'cert_length': 'cert_length',
        'subject_common_name': 'subject_common_name',
    }


class ShadowserverSandboxUrl201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.sandbox-url.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'sandbox-url',
        'origin': 'sandbox',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'md5': 'md5hash',
        'url': 'url',
        'fqdn': 'host',
        'method': 'method',
    }


class ShadowserverOpenResolver201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.open-resolver.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'resolver',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'fqdn': 'hostname',
        'dport': 'port',
        'proto': 'protocol',
        'min_amplification': 'min_amplification',
        'dns_version': 'dns_version',
    }


class ShadowserverRedis201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.redis.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'redis',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverMemcached201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.memcached.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'memcached',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverMongodb201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.mongodb.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'mongodb',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'visible_databases': 'visible_databases',
    }


class ShadowserverNatpmp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.natpmp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'nat-pmp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverMssql201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.mssql.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'mssql',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverElasticsearch201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.elasticsearch.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'elasticsearch',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverSslFreak201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ssl-freak.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ssl-freak',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'handshake': 'handshake',
        'cert_length': 'cert_length',
        'subject_common_name': 'subject_common_name',
    }

    def parse(self, data):
        parsed_gen = super(ShadowserverSslFreak201412Parser, self).parse(data)
        for item in parsed_gen:
            item['proto'] = 'tcp'
            yield item


class ShadowserverNtpMonitor201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ntp-monitor.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ntp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'proto': 'protocol',
        'dport': 'port',
    }


class ShadowserverPortmapper201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.portmapper.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'portmapper',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }

    def parse(self, data):
        parsed_gen = super(ShadowserverPortmapper201412Parser, self).parse(data)
        for item in parsed_gen:
            item['proto'] = 'udp'
            yield item


class ShadowserverMdns201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.mdns.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'mdns',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }

    def parse(self, data):
        parsed_gen = super(ShadowserverMdns201412Parser, self).parse(data)
        for item in parsed_gen:
            if item['proto'].lower() != 'udp':
                LOGGER.warning('Protocol is different from UDP - %r', item['proto'])
            yield item


class ShadowserverXdmcp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.xdmcp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'xdmcp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }

    def parse(self, data):
        parsed_gen = super(ShadowserverXdmcp201412Parser, self).parse(data)
        for item in parsed_gen:
            if item['proto'].lower() != 'udp':
                LOGGER.warning('Protocol is different from UDP - %r', item['proto'])
            yield item


class ShadowserverDb2201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.db2.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'db2',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'proto': 'protocol',
        'dport': 'port',
    }


class ShadowserverRdp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.rdp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'rdp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverTftp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.tftp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'tftp',
        'proto': 'udp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverIsakmp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.isakmp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'isakmp',
        'proto': 'udp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverTelnet201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.telnet.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'telnet',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverCwmp201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.cwmp.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'cwmp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverLdap201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ldap.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ldap',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverVnc201412Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.vnc.201412'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'vnc',
        'proto': 'tcp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': {'ip': 'ip'},
        'dport': 'port',
        'product': 'product',
    }


class ShadowserverSinkholeHttp202203Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.sinkhole-http.202203'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'sinkhole',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'src_ip',
        'dport': 'dst_port',
        'sport': 'src_port',
        'dip': 'dst_ip',
        'proto': 'protocol',
        'url': 'http_url',
        'fqdn': 'http_host',
        'name': 'infection',
    }


class ShadowserverSinkhole202203Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.sinkhole.202203'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'sinkhole',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'src_ip',
        'dport': 'dst_port',
        'sport': 'src_port',
        'dip': 'dst_ip',
        'proto': 'protocol',
        'name': 'infection',
    }


class ShadowserverDarknet202203Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.darknet.202203'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'bots',
        'origin': 'darknet',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'src_ip',
        'dport': 'dst_port',
        'dip': 'dst_ip',
        'proto': 'protocol',
        'name': 'infection',
    }


class ShadowserverModbus202203Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.modbus.202203'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'modbus',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'vendor': 'vendor',
        'revision': 'revision',
        'product_code': 'product_code',
    }


class ShadowserverIcs202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ics.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'name': 'tag',
        'device_vendor': 'device_vendor',
        'device_type': 'device_type',
        'device_model': 'device_model',
        'device_version': 'device_version',
        'device_id': 'device_id',
    }


class ShadowserverCoap202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.coap.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'coap',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverUbiquiti202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ubiquiti.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ubiquiti',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverArd202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ard.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'ard',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverRdpeudp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.rdpeudp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'rdpeudp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverDvrDhcpdiscover202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.dvr-dhcpdiscover.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'amplifier',
        'name': 'dvr-dhcpdiscover',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'device_vendor': 'device_vendor',
        'device_type': 'device_type',
        'device_model': 'device_model',
        'device_version': 'device_version',
        'device_id': 'device_id',
    }


class ShadowserverHttp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.http.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'name': 'tag',
    }


class ShadowserverMqtt202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.mqtt.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'mqtt',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverLdapTcp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ldap-tcp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ldap',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverRsync202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.rsync.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'rsync',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverRadmin202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.radmin.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'radmin',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverAdb202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.adb.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'adb',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'device_vendor': 'device_vendor',
        'device_type': 'device_type',
        'device_model': 'device_model',
        'device_version': 'device_version',
    }


class ShadowserverAfp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.afp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'afp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverCiscoSmartInstall202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.cisco-smart-install.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'cisco-smart-install',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


class ShadowserverIpp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.ipp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'ipp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'device_vendor': 'device_vendor',
        'device_type': 'device_type',
        'device_model': 'device_model',
        'device_version': 'device_version',
    }


class ShadowserverHadoop202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.hadoop.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'hadoop',
        'proto': 'tcp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
    }


class ShadowserverExchange202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.exchange.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'proto': 'tcp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'name': 'tag',
    }


class ShadowserverSmtp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.smtp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
        'name': 'tag',
    }


class ShadowserverAmqp202204Parser(_BaseShadowserverParser):

    default_binding_key = 'shadowserver.amqp.202204'
    constant_items = {
        'restriction': 'need-to-know',
        'confidence': 'medium',
        'category': 'vulnerable',
        'name': 'amqp',
    }

    n6_field_to_data_key_mapping = {
        'time': 'timestamp',
        'address': 'ip',
        'dport': 'port',
        'proto': 'protocol',
    }


add_parser_entry_point_functions(__name__)

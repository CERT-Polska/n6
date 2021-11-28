"""
Copyright (c) 2017-2021 NASK
Software Development Department

The IntelMQ Adapter component, responsible for converting data
between N6 and IntelMQ Systems.

Usage:
n6_to_intel_converter = N6ToIntelConverter()
message <str-JSON> = n6_to_intel_converter.convert(n6_message <str-JSON>)

intel_to_n6_converter = IntelToN6Converter()
n6_message <str-JSON> = intel_to_n6_converter.convert(intel_message <str-JSON>)

Source field                                               Destination field

convertible field                                          converted field
field unmappable to IntelMQ but known to N6                added to 'extra' <JSON>
field unmappable to N6 but known to IntelMQ                added to 'intelmq' <dict>
field unknown to either system                             ignored
"""

import bisect
import json
import logging
from collections.abc import MutableMapping
from copy import deepcopy


LOGGER = logging.getLogger(__name__)

#XXX: Perhaps the dictionaries below may need be moved to separate config file -
#     - but maybe it can be done as a refactoring task in the future.
INTEL_TO_N6_MAP = {
    '__type': '',
    'classification.identifier': '',
    'classification.taxonomy': '',
    'classification.type': '',
    'comment': '',
    'destination.abuse_contact': '',
    'destination.account': 'username',
    'destination.allocated': '',
    'destination.as_name': '',
    'destination.asn': '',
    'destination.fqdn': '',
    'destination.geolocation.cc': '',
    'destination.geolocation.city': '',
    'destination.geolocation.country': '',
    'destination.geolocation.latitude': '',
    'destination.geolocation.longitude': '',
    'destination.geolocation.region': '',
    'destination.geolocation.state': '',
    'destination.ip': 'dip',
    'destination.local_hostname': '',
    'destination.local_ip': '',
    'destination.network': '',
    'destination.port': 'dport',
    'destination.registry': '',
    'destination.reverse_dns': '',
    'destination.tor_node': '',
    'destination.url': '',
    'event_description.target': '',
    'event_description.text': '',
    'event_description.url': '',
    'event_hash': '',
    'feed.accuracy': '',
    'feed.code': '',
    'feed.documentation': '',
    'feed.name': '',
    'feed.provider': '',
    'feed.url': '',
    'malware.hash.md5': 'md5',
    'malware.hash.sha1': 'sha1',
    'malware.hash.sha256': '',
    'malware.name': 'name',  # only 'bots' category, other cases won't be affected
    'malware.version': '',
    'misp.attribute_uuid': 'misp_attr_uuid',
    'misp.event_uuid': 'misp_event_uuid',
    'output': '',
    'protocol.application': '',
    'protocol.transport': 'proto',
    'raw': '',
    'rtir_id': '',
    'screenshot_url': '',
    'source.abuse_contact': '',
    'source.account': '',
    'source.allocated': '',
    'source.as_name': '',
    'source.asn': 'asn',
    'source.fqdn': 'fqdn',
    'source.geolocation.cc': 'cc',
    'source.geolocation.city': '',
    'source.geolocation.country': '',
    'source.geolocation.cymru_cc': '',
    'source.geolocation.geoip_cc': '',
    'source.geolocation.latitude': '',
    'source.geolocation.longitude': '',
    'source.geolocation.region': '',
    'source.geolocation.state': '',
    'source.ip': 'ip',
    'source.local_hostname': '',
    'source.local_ip': '',
    'source.network': 'ip_network',
    'source.port': 'sport',
    'source.registry': '',
    'source.reverse_dns': 'rdns',
    'source.tor_node': '',
    'source.url': 'url',
    'status': '',
    'time.observation': '',
    'time.source': 'time',
}

N6_TO_INTEL_MAP = {
    '__preserved_custom_keys__': '',
    '__type': '',
    '_bl-current-time': '',
    '_bl-series-id': '',
    '_bl-series-no': '',
    '_bl-series-total': '',
    '_bl-time': '',
    'action': '',
    'additional_data': '',
    'address': '',
    'adip': '',
    'alternative_fqdns': '',
    'asn': 'source.asn',
    'botid': '',
    'category': '',
    'cc': 'source.geolocation.cc',
    'cert_length': '',
    'channel': '',
    'confidence': '',
    'count': '',
    'dataset': '',
    'description': '',
    'detected_since': '',
    'dip': 'destination.ip',
    'dir': '',
    'dns_version': '',
    'dport': 'destination.port',
    'email': '',
    'enriched': '',
    'expires': '',
    'facebook_id': '',
    'first_seen': '',
    'fqdn': 'source.fqdn',
    'handshake': '',
    'header': '',
    'iban': '',
    'id': '',
    'injects': '',
    'internal_ip': '',
    'ip': 'source.ip',
    'ip_network': 'source.network',
    'ipmi_version': '',
    'ipv6': 'source.ip',
    'mac_address': '',
    'md5': 'malware.hash.md5',
    'method': '',
    'min_amplification': '',
    'misp_attr_uuid': 'misp.attribute_uuid',
    'misp_event_uuid': 'misp.event_uuid',
    'misp_eventdid': '',
    'name': '',
    'origin': '',
    'phone': '',
    'product': '',
    'proto': 'protocol.transport',
    'proxy_type': '',
    'rdns': 'source.reverse_dns',
    'referer': '',
    'registrar': '',
    'replaces': '',
    'request': '',
    'restriction': '',
    'rid': '',
    'sender': '',
    'sha1': 'malware.hash.sha1',
    'source': '',
    'sport': 'source.port',
    'status': '',
    'subject_common_name': '',
    'sysdesc': '',
    'tags': '',
    'target': '',
    'time': 'time.source',
    'until': '',
    'url': 'source.url',
    'url_pattern': '',
    'urls_matched': '',
    'user_agent': '',
    'username': '',
    'version': '',
    'visible_databases': '',
    'x509fp_sha1': '',
    'x509issuer': '',
    'x509subject': ''
}

CLASSIFICATION_MAPPING = {
    'scanning': {'classification.taxonomy': 'Information Gathering',
                 'classification.identifier': 'scanning', 'classification.type': 'scanner'},
    'malware-action': {'classification.taxonomy': 'Malicious Code',
                       'classification.identifier': 'malware configuration',
                       'classification.type': 'malware configuration'},
    'amplifier': {'classification.taxonomy': 'Vulnerable',
                  'classification.identifier': 'amplifier',
                  'classification.type': 'vulnerable service'},
    'vulnerable': {'classification.taxonomy': 'Vulnerable',
                   'classification.identifier': 'vulnerable', 'classification.type': 'other'},
    'dos-attacker': {'classification.taxonomy': 'Availability',
                     'classification.identifier': 'dos-attacker', 'classification.type': 'ddos'},
    'dns-query': {'classification.taxonomy': 'Other', 'classification.identifier': 'ignore me',
                  'classification.type': 'other'},
    'tor': {'classification.taxonomy': 'Other', 'classification.identifier': 'tor exit node',
            'classification.type': 'tor'},
    'leak': {'classification.taxonomy': 'Information Content Security',
             'classification.identifier': 'leak', 'classification.type': 'leak'},
    'spam-url': {'classification.taxonomy': 'Abusive Content',
                 'classification.identifier': 'spam-url', 'classification.type': 'spam'},
    'backdoor': {'classification.taxonomy': 'Intrusions',
                 'classification.identifier': 'hacked server', 'classification.type': 'backdoor'},
    'other': {'classification.taxonomy': 'Vulnerable', 'classification.identifier': 'unknown',
              'classification.type': 'unknown'},
    'cnc': {'classification.taxonomy': 'Malicious Code', 'classification.identifier': 'c&c server',
            'classification.type': 'c&c'},
    'phish': {'classification.taxonomy': 'Fraud', 'classification.identifier': 'phishing',
              'classification.type': 'phishing'},
    'server-exploit': {'classification.taxonomy': 'Malicious Code',
                       'classification.identifier': 'server-exploit',
                       'classification.type': 'exploit'},
    'dos-victim': {'classification.taxonomy': 'Availability',
                   'classification.identifier': 'dos-victim', 'classification.type': 'ddos'},
    'proxy': {'classification.taxonomy': 'Vulnerable', 'classification.identifier': 'open proxy',
              'classification.type': 'proxy'},
    'malurl': {'classification.taxonomy': 'Malicious Code', 'classification.identifier': 'malurl',
               'classification.type': 'exploit'},
    'fraud': {'classification.taxonomy': 'Fraud', 'classification.identifier': 'fraud',
              'classification.type': 'account numbers'},
    'flow-anomaly': {'classification.taxonomy': 'Other',
                     'classification.identifier': 'flow-anomaly', 'classification.type': 'other'},
    'spam': {'classification.taxonomy': 'Abusive Content', 'classification.identifier': 'spam',
             'classification.type': 'spam'},
    'flow': {'classification.taxonomy': 'Other', 'classification.identifier': 'flow',
             'classification.type': 'other'},
    'webinject': {'classification.taxonomy': 'Malicious Code',
                  'classification.identifier': 'malware', 'classification.type': 'malware'},
    'sandbox-url': {'classification.taxonomy': 'ignore', 'classification.identifier': 'ignore me',
                    'classification.type': 'ignore'},
    'bots': {'classification.taxonomy': 'Malicious Code',
             'classification.identifier': 'generic-n6-drone',
             'classification.type': 'botnet drone'}
}

CLASSIFICATION_FIELDS = [
    'classification.taxonomy',
    'classification.identifier',
    'classification.type',
]

CONFIDENCE_TO_ACCURACY = {
    'low': 33.0,
    'medium': 66.0,
    'high': 100.0,
}


class BaseConverter(object):

    _mapping = NotImplemented
    _keylist = NotImplemented
    extra_field_name_in = NotImplemented
    extra_field_name_out = NotImplemented

    def __init__(self):
        self._extra_data = {}
        self._output_dict = {}
        self._address_list = []

    def _convert_specific(self, data):
        """
        To be overriden by subclasses.
        Handle cases specific for each subclass.
        Args:
            data: dict
        """
        raise NotImplementedError

    def convert(self, source_data):
        """
        Handle common elements in converted data
        Args:
            source_data: str (JSON)
        Returns:
            output_data: str (JSON)
        """
        self._extra_data.clear()
        self._output_dict.clear()
        self._address_list = []
        data = json.loads(source_data)
        if self.extra_field_name_in in data:
            self._unpack_extra_data(data.pop(self.extra_field_name_in))
        self._convert_specific(data)
        for source_key, value in data.items():
            destination_key = self._mapping.get(source_key)
            if not destination_key or destination_key == 'id':  # IntelMQ -> N6 'feed_id' field
                if source_key in self._mapping:
                    self._extra_data[source_key] = value
            else:
                self._output_dict[destination_key] = value
        if self._extra_data:
            extra_json = self._adjust_extra_data(self._extra_data)
            self._output_dict[self.extra_field_name_out] = extra_json
        for output_data in self._final_process_data():
            output_data_json = json.dumps(output_data)
            yield output_data_json

    def _final_process_data(self):
        yield self._output_dict

    def _unpack_extra_data(self, received_extra_data):
        """
        Extract destination-only-typical fields
        from 'extra' field and other fields
        """
        if not isinstance(received_extra_data, MutableMapping):
            received_extra_data = json.loads(received_extra_data)
        for key, value in received_extra_data.items():
            if key in self._keylist:
                self._output_dict[key] = value
            elif key == 'feed_id':
                self._output_dict['id'] = value
            else:
                if key in self._mapping:
                    self._extra_data[key] = value

    @staticmethod
    def _adjust_extra_data(extra_data):
        """
        Override this method to keep 'extra' values
        as json - required by intelmq, no modification
        needed for n6
        """
        return extra_data


class N6ToIntelConverter(BaseConverter):

    # name for field (in incoming messages) holding data
    # that cannot be parsed by N6 components.
    extra_field_name_in = 'intelmq'

    # name for field (created for outcoming messages)
    # holding data specific for N6;
    # that data will not be parsed by IntelMQ bots.
    extra_field_name_out = 'n6_data'

    def __init__(self):
        self._mapping = N6_TO_INTEL_MAP
        self._keylist = INTEL_TO_N6_MAP.keys()
        super(N6ToIntelConverter, self).__init__()

    def _convert_specific(self, data):
        address = data.pop('address', None)
        if address:
            self._extract_address_fields(address)
        if 'id' in data:
            self._extra_data['feed_id'] = data.pop('id')
        if 'fqdn' in data:
            fqdn = data.pop('fqdn')
            if fqdn == 'unknown':
                self._extra_data['fqdn'] = fqdn
            else:
                self._output_dict['source.fqdn'] = fqdn
        self._set_classification(data)
        confidence = data.pop('confidence', None)
        if confidence:
            self._output_dict['feed.accuracy'] = CONFIDENCE_TO_ACCURACY[confidence]
        name = data.pop('name', None)
        if 'malware.name' not in self._output_dict and name:
            self._extra_data['name'] = name

    def _final_process_data(self):
        """
        If more than one address is found,
        make a separate message for each address.

        Returns:
            dictionary or list
        """
        if self._address_list:
            for single_addr in self._address_list:
                new_dict = deepcopy(self._output_dict)
                new_dict.update(single_addr)
                yield new_dict
        else:

            yield self._output_dict

    def _set_classification(self, data):
        category = data.pop("category", None)
        if category:
            for field in CLASSIFICATION_FIELDS:
                self._output_dict[field] = CLASSIFICATION_MAPPING[category][field]
            if category == 'bots':
                name = data.pop('name', None)
                if name:
                    self._output_dict['malware.name'] = name
                    self._output_dict['classification.identifier'] = name
                else:
                    self._output_dict['classification.identifier'] = 'generic-n6-drone'

    def _extract_address_fields(self, address):
        for single_addr in address:
            temp_dict = {}
            for source_key, value in single_addr.items():
                destination_key = self._mapping.get(source_key)
                temp_dict[destination_key] = value
            self._address_list.append(temp_dict)

    @staticmethod
    def _adjust_extra_data(extra_data):
        """
        The 'extra' field will be in json format.
        """
        return json.dumps(extra_data)


class IntelToN6Converter(BaseConverter):

    # name for field (in incoming messages) holding data
    # that cannot be parsed by IntelMQ bots.
    extra_field_name_in = 'n6_data'

    # name for field (created for outcoming messages)
    # holding data specific for IntelMQ;
    # that data will not be parsed by N6 components.
    extra_field_name_out = 'intelmq'

    def __init__(self):
        self._mapping = INTEL_TO_N6_MAP
        self._keylist = N6_TO_INTEL_MAP.keys()
        super(IntelToN6Converter, self).__init__()

    def _convert_specific(self, data):
        self._set_address(data)
        self._set_category_or_add_classification_fields(data)
        accuracy = data.pop('feed.accuracy', None)
        if accuracy is not None:  # because (theoretically) value 0 is possible.
            grades = ['low', 'medium', 'high']
            thresholds = [34, 67]
            value = bisect.bisect(thresholds, accuracy)
            self._output_dict['confidence'] = grades[value]

    def _set_category_or_add_classification_fields(self, data):
        category = None
        if all(field in data for field in CLASSIFICATION_FIELDS):
            category = self._get_n6_category_from_mapping(data)
            if category:
                self._output_dict['category'] = category
            else:
                LOGGER.warning("All classification fields present, "
                               "but could not establish category for the source")
        if not category:
            # no need to log as from source intelmq data category can't be established.
            # add classification.* fields to 'extra'
            for field in CLASSIFICATION_FIELDS:
                if field in data:
                    self._extra_data[field] = data.pop(field)

    @staticmethod
    def _get_n6_category_from_mapping(data):
        for key, val in CLASSIFICATION_MAPPING.items():
            # in accordance with mapping, exception for 'bots' category
            if all((val[field].lower() == data[field].lower()
                    or data[field] == data.get('malware.name'))
                   for field in CLASSIFICATION_FIELDS):
                for classification_field in val.keys():
                    data.pop(classification_field)
                return key

    def _set_address(self, data):
        """
        The fields, after being converted in standard way
        by `convert` method, now are 'packed'
        into `address` list of dictionaries
        """
        address = {}
        for field in ['ip', 'ipv6', 'cc', 'asn', 'dir', 'rdns']:
            if N6_TO_INTEL_MAP[field] in data:
                address[field] = data.pop(N6_TO_INTEL_MAP[field])
        if address:
            self._output_dict['address'] = [address]

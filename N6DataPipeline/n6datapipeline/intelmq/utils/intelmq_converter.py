# Copyright (c) 2017-2021 NASK. All rights reserved.

"""
The IntelMQ Adapter component, responsible for converting data
between N6 and IntelMQ Systems.

Usage:
n6_to_intel_converter = N6ToIntelConverter
message <str-JSON> = n6_to_intel_converter(n6_message: bytes, routing_key: str).convert()

intel_to_n6_converter = IntelToN6Converter
n6_message <str-JSON> = intel_to_n6_converter(intelmq_message: bytes, routing_key: str).convert()

Source field                                               Destination field

convertible field                                          converted field
field unmappable to IntelMQ but known to N6                added to 'extra' <JSON>
field unmappable to N6 but known to IntelMQ                added to 'intelmq' <dict>
field unknown to either system                             ignored
"""

import bisect
import datetime
import json
import logging
import time
from copy import deepcopy
from math import trunc
from typing import (
    Any,
    Generator,
    MutableMapping,
    MutableSequence,
    Union,
)
from unittest.mock import Mock

from n6datapipeline.intelmq import (
    INTELMQ_EXTRA_DATA_FIELD_NAME,
    N6_EXTRA_DATA_FIELD_NAME,
)
from n6datapipeline.intelmq.helpers import BaseParserExtended
from n6datasources.collectors.base import BaseCollector
from n6lib.common_helpers import ascii_str
from n6lib.const import EVENT_TYPE_ENUMS
from n6lib.data_spec import FieldValueError
from n6lib.record_dict import RecordDict
from n6lib.unit_test_helpers import MethodProxy


LOGGER = logging.getLogger(__name__)

# XXX: Perhaps the dictionaries below may need to be moved to
# a separate config file - but maybe it can be done as a refactoring
# task in the future.
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
    'gca_specific': '',
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


class BaseConverter:

    _mapping = NotImplemented
    _keylist = NotImplemented
    extra_field_name_in = NotImplemented
    extra_field_name_out = NotImplemented

    webinput_routing_state = 'intelmq-webinput-csv'

    def __init__(self, source_data: bytes, routing_key: str) -> None:
        """
        Args:
            source_data: bytes (JSON)
                Input data fetched from the pipeline.
            routing_key: str
                The "routing key" of incoming message.
        """
        self._input_routing_key = routing_key
        self._raw_data = source_data
        self._parsed_data = self._get_parsed_data(source_data)
        self._extra_data = {}
        self._output_dict = self._get_output_dict()
        self._address_list = []

    def _convert_specific(self, data: dict) -> None:
        """
        To be overriden by subclasses.
        Handle cases specific for each subclass.
        Args:
            data (dict):
                Deserialized incoming data.
        """
        raise NotImplementedError

    def convert(self) -> Generator[Union[bytes, str], None, None]:
        """
        Handle common elements in converted data.

        Yields:
            output_data (bytes/str) (JSON):
                A processed object, optionally iterated from
                the incoming data JSON object.
        """
        if self.extra_field_name_in in self._parsed_data:
            self._unpack_extra_data(self._parsed_data.pop(self.extra_field_name_in))
        self._convert_specific(self._parsed_data)
        for source_key, value in self._parsed_data.items():
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
            yield self._dump_output_data(output_data)

    @staticmethod
    def _get_parsed_data(source_data: Union[bytes, str]) -> dict:
        return json.loads(source_data)

    def _get_output_dict(self) -> MutableMapping:
        return dict()

    def _final_process_data(self):
        yield self._output_dict

    def _dump_output_data(self,
                          output_data: Union[MutableMapping, MutableSequence]
                          ) -> Union[bytes, str]:
        return json.dumps(output_data)

    def _unpack_extra_data(self, received_extra_data):
        """
        Extract destination-only-typical fields
        from 'extra' field and other fields
        """
        if not isinstance(received_extra_data, MutableMapping):
            received_extra_data = json.loads(received_extra_data)
        for key, value in received_extra_data.items():
            if not self._extra_field_handle_hook(key, value):
                # proceed if the field has not been handled separately
                if key in self._keylist:
                    self._output_dict[key] = value
                elif key in self._mapping:
                        self._extra_data[key] = value

    @staticmethod
    def _adjust_extra_data(extra_data):
        """
        Override this method to keep 'extra' values
        as json - required by intelmq, no modification
        needed for n6
        """
        return extra_data

    # noinspection PyMethodMayBeStatic
    def _extra_field_handle_hook(self, key: str, value: Any) -> bool:
        """
        Override the method in case there are fields that need to
        be handled individually when they are being unpacked from
        the 'extra' storage field.

        Args:
            key (str):
                Name of the field currently yielded by the iterator.
            value:
                Field's value.
        Returns:
            True if the field has been handled, False if it has been
            ignored.
        """
        return False


class N6ToIntelConverter(BaseConverter):

    # name for field (in incoming messages) holding data
    # that cannot be parsed by N6 components.
    extra_field_name_in = INTELMQ_EXTRA_DATA_FIELD_NAME

    # name for field (created for outcoming messages)
    # holding data specific for N6;
    # that data will not be parsed by IntelMQ bots.
    extra_field_name_out = N6_EXTRA_DATA_FIELD_NAME

    def __init__(self, *args, **kwargs):
        self._mapping = N6_TO_INTEL_MAP
        self._keylist = INTEL_TO_N6_MAP.keys()
        super(N6ToIntelConverter, self).__init__(*args, **kwargs)

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
        confidence = data.get('confidence')
        # if 'feed.accuracy' is already in the output dict (it has been
        # restored from extra data), do not overwrite its value
        if confidence and 'feed.accuracy' not in self._output_dict:
            self._output_dict['feed.accuracy'] = CONFIDENCE_TO_ACCURACY[confidence]
            # do not store 'confidence' in the extra field if it
            # has been converted to IntelMQ's 'feed.accuracy'
            data.pop('confidence')

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
        category = data.get('category')
        # set "classification fields" based on n6-format field
        # 'category', only if none of them has been restored from
        # extra data
        if category and all(field not in self._output_dict for field in CLASSIFICATION_FIELDS):
            category_mapping = CLASSIFICATION_MAPPING.get(category)
            if category_mapping:
                self._output_dict.update(category_mapping)
                # do not store 'category' in the extra field after
                # its value has been converted to the set
                # of IntelMQ's classification fields
                data.pop('category')
            else:
                self._output_dict.update({field: CLASSIFICATION_MAPPING['other'][field]
                                          for field in CLASSIFICATION_FIELDS})
            if category == 'bots':
                name = data.get('name')
                if name and 'malware.name' not in self._output_dict:
                    self._output_dict['malware.name'] = name
                    self._output_dict['classification.identifier'] = name
                    data.pop('name')
                elif 'classification.identifier' not in self._output_dict:
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


class IntelToN6RecordDict(RecordDict):

    __required_fields_missing_in_intelmq_data = [
        'confidence',
        'id',
        'restriction',
        'rid',
        'source',
        'time',
    ]
    __default_source_provider = 'default'
    __field_value_error_msg_template = ("The {!a} field of the message has not been converted "
                                        "from any of the IntelMQ message's field values, "
                                        "and the attempt to generate it from the message's "
                                        "routing key has failed")

    def __init__(self, raw_data: bytes,
                 extra_data: dict,
                 input_routing_key: str,
                 webinput_routing_state: str,
                 *args, **kwargs) -> None:
        self.__raw_data = raw_data
        self.__extra_data = extra_data
        self.__input_routing_key = input_routing_key
        self.__webinput_routing_state = webinput_routing_state
        self.__base_collector_proxy = self.__get_method_proxy(BaseCollector)
        # noinspection PyProtectedMember
        parser_mock_kwargs = {
            '_iter_output_id_base_items': BaseParserExtended._iter_output_id_base_items,
        }
        self.__base_parser_proxy = self.__get_method_proxy(BaseParserExtended,
                                                           **parser_mock_kwargs)
        super().__init__(*args, **kwargs)

    def __getitem__(self, item):
        if item in self.__required_fields_missing_in_intelmq_data and item not in self._dict:
            self.__setitem__(item, getattr(self, f'_IntelToN6RecordDict__{item}'))
        return super().__getitem__(item)

    def get_ready_dict(self):
        """
        Extend the method to try to get values of the result dict's
        keys, which are required by n6 components, but they might not
        have been converted from the corresponding IntelMQ field
        values.

        When trying to get the key's value, the `__getitem__()`
        extended method is being called. If the key is not in the dict,
        get its default or generated value from the corresponding
        property, and then set it as value of a newly created
        `IntelToN6RecordDict` key, using the `__setitem__()` method.
        """
        # noinspection PyStatementEffect
        self['confidence']
        # noinspection PyStatementEffect
        self['restriction']
        # noinspection PyStatementEffect
        self['source']
        # noinspection PyStatementEffect
        self['rid']
        # noinspection PyStatementEffect
        self['time']
        # get the 'id' key as the last one, so if it has not been
        # set yet, then its value, event's ID, will be generated
        # when all other fields are set
        # noinspection PyStatementEffect
        self['id']
        return super().get_ready_dict()

    @staticmethod
    def __get_method_proxy(cls, **kwargs):
        """
        Get a method proxy of the class in order to call its methods
        without having to create its instance.

        This workaround is used so the required methods do not have
        to be implemented again, to prevent code duplication.
        """
        moc = Mock(**kwargs)
        return MethodProxy(cls, moc)

    #
    # properties return default or generated values of the fields
    # that are required by n6 components but have not been
    # converted from corresponding IntelMQ field values

    @property
    def __confidence(self):
        return 'low'

    @property
    def __id(self):
        # noinspection PyProtectedMember
        return self.__base_parser_proxy._get_output_message_id(self)

    @property
    def __restriction(self):
        return 'public'

    @property
    def __rid(self):
        rid_from_data = self.__extra_data.get('rid')
        if rid_from_data is None:
            return self.__base_collector_proxy.get_output_message_id(
                source=self['source'],
                created_timestamp=trunc(time.time()),
                output_data_body=self.__raw_data)
        return rid_from_data

    @property
    def __source(self):
        rk_parts = self.__input_routing_key.split('.')
        if len(rk_parts) < 2:
            msg = (f"{self.__field_value_error_msg_template.format('source')}: cannot generate "
                   f"the 'source' field value from the message's routing key "
                   f"({ascii_str(self.__input_routing_key)!a}) that does not consist of at least "
                   f"two parts")
            raise FieldValueError(public_message=msg)
        if len(rk_parts) >= 3:
            # In case of the routing key consists of three or more
            # parts, check if the last one is not a 'raw format's
            # version tag', and remove it, if this is the case.
            try:
                int(rk_parts[-1])
            except ValueError:
                pass
            else:
                rk_parts = rk_parts[:-1]
        if rk_parts[-2] in EVENT_TYPE_ENUMS:
            # if for some reason the part of the routing key, which
            # is a candidate for the "source provider", is an
            # indicator of the event type, replace it with default
            # value
            LOGGER.warning("The 'source provider' part of the 'source' field, extracted from "
                           "message's routing key, has a value which is an indicator of "
                           "the event's type, so it will be changed to default value")
            rk_parts[-2] = self.__default_source_provider
        # Use only the last two parts of the message's routing key.
        # Sample format of the routing key from IntelMQ's bot
        # integrated into n6 pipeline:
        # <event type>.<bot's ID>.<source provider>.<source channel>
        # Only the "source provider" and "source channel" parts should
        # be used.
        return '.'.join((rk_parts[-2], rk_parts[-1]))

    @property
    def __time(self):
        return str(datetime.datetime.utcnow().replace(microsecond=0))


class IntelToN6Converter(BaseConverter):

    # name for field (in incoming messages) holding data
    # that cannot be parsed by IntelMQ bots.
    extra_field_name_in = N6_EXTRA_DATA_FIELD_NAME

    # name for field (created for outcoming messages)
    # holding data specific for IntelMQ;
    # that data will not be parsed by N6 components.
    extra_field_name_out = INTELMQ_EXTRA_DATA_FIELD_NAME

    default_category = 'other'
    default_confidence = 'low'
    default_restriction = 'public'

    def __init__(self, *args, **kwargs):
        self._mapping = INTEL_TO_N6_MAP
        self._keylist = N6_TO_INTEL_MAP.keys()
        self._name_from_extra_data = None
        super(IntelToN6Converter, self).__init__(*args, **kwargs)

    def _get_output_dict(self) -> RecordDict:
        return IntelToN6RecordDict(raw_data=self._raw_data,
                                   extra_data=self._extra_data,
                                   input_routing_key=self._input_routing_key,
                                   webinput_routing_state=self.webinput_routing_state)

    def _extra_field_handle_hook(self, key: str, value: Any) -> bool:
        if key == 'name' and 'category' not in self._output_dict:
            # if the 'category' field has not been set yet, postpone
            # unpacking the 'name' from "extra" data - it is illegal
            # to set it when there is no 'category', it will cause
            # an error
            self._name_from_extra_data = value
            return True
        if key == 'category' and self._name_from_extra_data is not None:
            # the 'name' field has been handled first, and because
            # of absence of 'category', saving it in output dict has
            # been postponed, but now 'category' is here, so also
            # the 'name' can be saved
            self._output_dict['category'] = value
            self._output_dict['name'] = self._name_from_extra_data
            return True
        if key == 'feed_id':
            self._output_dict['id'] = value
            return True
        return False

    def _convert_specific(self, data: dict) -> None:
        self._set_address(data)
        self._set_category_or_add_classification_fields(data)
        accuracy = data.get('feed.accuracy')
        # because (theoretically) value 0 is possible
        if accuracy is not None and 'confidence' not in self._output_dict:
            grades = ['low', 'medium', 'high']
            thresholds = [34, 67]
            value = bisect.bisect(thresholds, accuracy)
            self._output_dict['confidence'] = grades[value]
            # remove IntelMQ's 'feed.accuracy' after it has been
            # converted to n6's 'confidence'
            data.pop('feed.accuracy')

    def _set_category_or_add_classification_fields(self, data):
        # generate the 'category' field's value, only if the field
        # has not been restored from extra data
        if 'category' not in self._output_dict:
            category = None
            if all(field in data for field in CLASSIFICATION_FIELDS):
                category = self._get_n6_category_from_mapping(data)
                if category:
                    self._output_dict['category'] = category
                else:
                    LOGGER.warning("All classification fields present, "
                                   "but could not establish category for the source. Using "
                                   "default category: {!r}".format(self.default_category))
                    self._output_dict['category'] = self.default_category
            if not category:
                # add classification.* fields to 'extra'
                LOGGER.warning("Could not establish category for the source. Using default "
                               "category: {!r}".format(self.default_category))
                self._output_dict['category'] = self.default_category
            if self._name_from_extra_data is not None:
                # restore the 'name' field now from "extra" data if it
                # has been postponed due to lack of 'category'
                self._output_dict['name'] = self._name_from_extra_data

    def _dump_output_data(self,
                          output_data: RecordDict
                          ) -> Union[bytes, str]:
        return output_data.get_ready_json()

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

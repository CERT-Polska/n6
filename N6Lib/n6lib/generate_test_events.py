# Copyright (c) 2013-2021 NASK. All rights reserved.

import copy
import datetime
import hashlib
import random
import re
import socket
import string
import urllib.parse

import radar

from n6lib.common_helpers import as_bytes
from n6lib.config import ConfigMixin
from n6lib.const import (
    CATEGORY_ENUMS,
    CONFIDENCE_ENUMS,
    ORIGIN_ENUMS,
    PROTO_ENUMS,
    STATUS_ENUMS,
)
from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


class AttributeCreationError(Exception):
    """
    Exception raised when no way of creating an attribute could
    be found.
    """


class RandomEvent(ConfigMixin):

    """
    A class used to generate random events.

    Its instance contains a generated event. There is a static method
    `generate_multiple_event_data()` that helps to create the given
    number of events.

    To create a new event attribute, first its name should be added
    to the 'possible_event_attributes' list in config. Next step can
    be done in several ways:

    * By creating a method, named like the new event attribute with
    the prefix same as it is set in `_GETTER_PREFIX`, individually
    handling the generation of the attribute.

    * By adding a new instance (or a class) attribute, named like the
    new event attribute, with the prefix set in
    `_POSSIBLE_VALS_PREFIX`, containing a list of possible values.
    Event will include randomly chosen value from the list.

    * By adding the attribute's name to the `port_values` list in
     the config, if it is a port number, or the `md5_values` list, if
     it is an MD5 hash value. A proper value will be returned
     for this kind of attribute.

    In last two cases, values in `_params`, if available, have
    a priority.

    If there is no method to handle the attribute, but its name
    is in `possible_event_attributes`, attribute's value still
    will be searched for in the `_params` attribute.

    By default, it is randomly chosen, based on the
    `_RANDOM_CHOICE_CRITERION`, if an attribute will be
    included in an event. To force it to be always included,
    add it to the `required_attributes` list in the config.
    """

    config_spec = '''
    [generator_rest_api]
    possible_event_attributes :: json
    required_attributes :: json
    dip_categories :: json
    port_values :: json
    md5_values :: json
    possible_cc_codes :: json
    possible_client :: json
    possible_domains :: json
    possible_url :: json
    possible_restriction :: json
    possible_source :: json
    possible_target :: json
    event_name=test event
    seconds_max :: int
    expires_days_max :: int
    random_ips_max :: int
    '''
    _GETTER_PREFIX = '_get_'
    _POSSIBLE_VALS_PREFIX = '_possible_'
    _RANDOM_CHOICE_CRITERION = (True, True, False)
    # regexes used for a simple validation of an input data from
    # special parameters (fqdn.sub and url.sub)
    _LEGAL_FQDN_REGEX = re.compile(r'[a-zA-Z0-9\.-]*', re.ASCII)
    _LEGAL_URL_REGEX = re.compile(r'[a-zA-Z0-9\.-\/:]*', re.ASCII)

    @staticmethod
    def generate_multiple_event_data(num_of_events,
                                     settings=None,
                                     access_zone=None,
                                     client_id=None,
                                     params=None):
        """
        Generate a given number of random events.

        Args/kwargs:
            `num_of_events`:
               A number of random events to generate.
            `settings` (optional; default: None):
                A dict containing Pyramid-like settings,
                that will override a configuration from config files,
                or append them.
            `access_zone` (optional; default: None):
                Access zone of a user making the request.
            `client_id`:
                Name of a client making the request.
            `params` (optional; default: None):
                Parameters from the request.

        Yields:
            Generated random events.
        """
        for _ in range(num_of_events):
            yield RandomEvent(
                params=params,
                settings=settings,
                access_zone=access_zone,
                client_id=client_id).event

    def __init__(self, settings=None, params=None, access_zone=None, client_id=None):
        self._config_init(settings)
        self._params = {}
        if params is not None:
            self._params = copy.deepcopy(params)
        self._access_zone = access_zone
        self._client_id = client_id
        self._max_ip = 0xfffffffe  # 255.255.255.254
        self._current_datetime = datetime.datetime.utcnow()
        self._attributes_init()

    def _config_init(self, settings):
        self.config = self.get_config_section(settings)
        self._possible_attrs = self.config.get('possible_event_attributes')
        self._required_attrs = self.config.get('required_attributes')
        self._event_name = self.config.get('event_name')
        self._dip_categories = self.config.get('dip_categories')
        self._possible_cc_codes = self.config.get('possible_cc_codes')
        self._possible_client = self.config.get('possible_client')
        self._possible_domains = self.config.get('possible_domains')
        self._possible_url = self.config.get('possible_url')
        self._possible_source = self.config.get('possible_source')
        self._possible_restriction = self.config.get('possible_restriction')
        self._possible_target = self.config.get('possible_target')
        self._port_values = self.config.get('port_values')
        self._md5_values = self.config.get('md5_values')
        self._seconds_max = self.config.get('seconds_max')
        self._expires_days_max = self.config.get('expires_days_max')
        self._random_ips_max = self.config.get('random_ips_max')

    def _attributes_init(self):
        self._possible_category = CATEGORY_ENUMS
        self._possible_confidence = CONFIDENCE_ENUMS
        self._possible_origin = ORIGIN_ENUMS
        self._possible_proto = PROTO_ENUMS
        self._possible_status = STATUS_ENUMS
        self.event = dict()
        for attr in self._possible_attrs:
            output_attribute = None
            try:
                output_attribute = self._create_attribute(attr)
            except AttributeCreationError:
                LOGGER.warning("No method could be assigned for attribute: '%s' and no values "
                               "were provided in request params.", attr)
            if output_attribute is not None:
                self.event[attr] = output_attribute

    def _create_attribute(self, attr):
        """
        Create an attribute in one of four ways:
        * using an available specific creator method,
        * using a general creator method,
        * based on the request param's values,
        * using the default method by randomly choosing value from
          the possible values.

        Args:
           `attr` (str): an attribute name.

        Returns:
            Value of the attribute or None if it could not be created.

        Raises:
            An `AttributeCreationError` if no specific method,
            associated request params or possible values for
            the attribute could be found.
        """
        attribute_getter = getattr(self, self._GETTER_PREFIX + attr, None)
        if attribute_getter:
            return attribute_getter()
        if self._attr_in_params(attr):
            return random.choice(self._params[attr])
        # if attribute was not handled by a specific method and it
        # was not found in params, choose randomly whether it
        # should be included
        if not self._include_in_event(attr):
            return None
        if attr in self._port_values:
            return self._get_value_for_port_attr()
        if attr in self._md5_values:
            return self._get_value_for_md5_attr()
        possible_vals = getattr(self, self._POSSIBLE_VALS_PREFIX + attr, None)
        # if there is no specific method for a current attribute
        # and values are not provided in request params, create
        # an attribute from possible values
        if possible_vals:
            return self._create_attr_from_possible_vals(possible_vals)
        # if no condition was met, raise an exception
        raise AttributeCreationError

    # FIXME later: This method is similar to RecordDict.iter_db_items()
    def generate_database_rows(self):
        event = copy.deepcopy(self.event)
        event['custom'] = {'enriched': event.pop('enriched')}
        event["ip"] = None
        event["cc"] = None
        event["asn"] = None
        if not event["address"]:
            event["address"] = None
            yield event
        else:
            for addr in event["address"]:
                result = copy.deepcopy(event)
                result.update(addr)
                yield result

    # general attribute creator methods
    @staticmethod
    def _create_attr_from_possible_vals(possible_vals):
        return random.choice(possible_vals)

    def _get_value_for_md5_attr(self):
        random_str = ''.join(
            random.choice(string.ascii_letters + string.digits) for _ in range(32)
        )
        return hashlib.md5(as_bytes(random_str)).hexdigest()

    def _get_value_for_port_attr(self):
        return random.randint(1, 2**16 - 1)

    # specific attribute creator methods
    def _get_address(self):
        param_ip_list = self._params.get('ip')
        param_asn_list = self._params.get('asn')
        param_cc_list = self._params.get('cc')
        non_empty_params = param_ip_list or param_asn_list or param_cc_list
        if self.event["category"] in self._dip_categories:
            num_ips = 1
        elif non_empty_params:
            num_ips = random.randint(1, len(non_empty_params))
        else:
            num_ips = random.randint(0, self._random_ips_max)
        result = []
        for i in range(num_ips):
            if param_ip_list:
                ip = random.choice(param_ip_list)
            else:
                ip = self._int_to_ip(random.randint(1, self._max_ip))
            asn = None
            cc = None
            # do not include asn or cc if opt.primary param is True
            if self._is_opt_primary():
                include_asn_cc = False
            # if params provide 'asn' or 'cc' attributes - include them,
            # otherwise - choose randomly
            elif param_asn_list or param_cc_list:
                include_asn_cc = True
            else:
                include_asn_cc = random.choice(self._RANDOM_CHOICE_CRITERION)
            if include_asn_cc:
                if param_asn_list:
                    asn = random.choice(param_asn_list)
                else:
                    asn = random.randint(1000, 5000)
                if param_cc_list:
                    cc = random.choice(param_cc_list)
                else:
                    cc = random.choice(self._possible_cc_codes)
            address_item = {
                key: value for key, value in [('ip', ip), ('asn', asn), ('cc', cc)]
                if value is not None}
            result.append(address_item)
        if result:
            return result
        return None

    def _get_client(self):
        # in case of the 'inside' access zone, client should get events
        # assigned only to him
        attr_name = 'client'
        if self._access_zone == 'inside':
            return [self._client_id]
        if self._attr_in_params(attr_name):
            return self._params[attr_name]
        if self._include_in_event(attr_name):
            return [random.choice(self._possible_client)]
        return None

    def _get_dip(self):
        attr_name = 'dip'
        if self.event["category"] in self._dip_categories:
            if self._attr_in_params(attr_name):
                return random.choice(self._params[attr_name])
            if self._include_in_event(attr_name):
                return self._int_to_ip(random.randint(1, self._max_ip))
        return None

    def _get_expires(self):
        max_expires = self._current_datetime + datetime.timedelta(days=self._expires_days_max)
        if self._include_in_event('expires'):
            return radar.random_datetime(self._current_datetime, max_expires)
        return None

    def _get_fqdn(self):
        if self.event['category'] in self._dip_categories or self._is_opt_primary():
            return None
        if self._attr_in_params('fqdn'):
            return random.choice(self._params['fqdn'])
        if self._attr_in_params('fqdn.sub'):
            sub = random.choice(self._params['fqdn.sub'])
            cleaned_sub = self._clean_input_value(sub, self._LEGAL_FQDN_REGEX)
            return self._get_matching_values(cleaned_sub, self._possible_domains)
        if self._is_opt_primary() or not self._include_in_event('fqdn'):
            return None
        if self._attr_in_params('url'):
            return self._url_to_domain(self.event['url'])
        return random.choice(self._possible_domains)

    def _get_modified(self):
        if self._include_in_event('modified'):
            return radar.random_datetime(self.event['time'], self._current_datetime)
        return None

    def _get_name(self):
        attr_name = 'name'
        if self._attr_in_params(attr_name):
            return random.choice(self._params[attr_name])
        if self._include_in_event(attr_name):
            return self._event_name
        return None

    def _get_proto(self):
        attr_name = 'proto'
        if self.event["category"] in self._dip_categories:
            if self._attr_in_params(attr_name):
                return random.choice(self._params[attr_name])
            elif self._include_in_event(attr_name):
                return random.choice(self._possible_proto)
        return None

    def _get_time(self):
        delta = datetime.timedelta(seconds=-random.randint(0, self._seconds_max))
        hour = datetime.timedelta(hours=1)
        if self._attr_in_params('time.max'):
            time_max = self._params['time.max'][0]
        else:
            time_max = self._current_datetime
        if self._attr_in_params('time.min'):
            time_min = self._params['time.min'][0]
        elif self._attr_in_params('time.until'):
            time_min = self._params['time.min'][0] + hour
        else:
            time_min = self._current_datetime + delta
        if self._include_in_event('time'):
            return str(radar.random_datetime(time_min, time_max))
        return None

    def _get_url(self):
        if self.event["category"] in self._dip_categories or self._is_opt_primary():
            return None
        if self._attr_in_params('url'):
            return random.choice(self._params['url'])
        if self._attr_in_params('url.sub'):
            sub = random.choice(self._params['url.sub'])
            cleaned_sub = self._clean_input_value(sub, self._LEGAL_URL_REGEX)
            return self._get_matching_values(cleaned_sub, self._possible_url)
        if self._include_in_event('url'):
            return random.choice(self._possible_url)
        return None

    def _get_sha1(self):
        attr_name = 'sha1'
        if self._attr_in_params(attr_name):
            return random.choice(self._params[attr_name])
        if self._include_in_event(attr_name):
            random_str = ''.join(
                random.choice(string.ascii_letters + string.digits) for _ in range(40)
            )
            return hashlib.sha1(as_bytes(random_str)).hexdigest()
        return None

    def _get_sha256(self):
        attr_name = 'sha256'
        if self._attr_in_params(attr_name):
            return random.choice(self._params[attr_name])
        if self._include_in_event(attr_name):
            random_str = ''.join(
                random.choice(string.ascii_letters + string.digits) for _ in range(64)
            )
            return hashlib.sha256(as_bytes(random_str)).hexdigest()
        return None

    @staticmethod
    def _int_to_ip(int_ip):
        return socket.inet_ntoa(int_ip.to_bytes(4, 'big'))

    @staticmethod
    def _url_to_domain(url):
        parsed_url = urllib.parse.urlparse(url)
        return parsed_url.hostname

    @staticmethod
    def _get_matching_values(sub, values):
        """
        Get all the values containing current subsequence.

        Args:
            `sub`: checked subsequence of characters.
            `values`: sequence of verified values.

        Returns:
            Random value containing subsequence, None if there are not
            any.
        """
        result = []
        # XXX: 1) both `.*` fragments seem not necessary; 2) shouldn't `sub` be `re.escape()`-ed?
        #      (or maybe some non-regex-based technique should be employed?)
        regex = re.compile('.*' + sub + '.*', re.ASCII)
        for value in values:
            match = regex.search(value)
            if match:
                result.append(match.group(0))
        if result:
            return random.choice(result)
        return None

    @staticmethod
    def _clean_input_value(val, regex):
        """
        Match only characters fitting to a pattern, up to a first
        illegal character.

        Args:
            `val`: string to be checked.
            `regex`: compiled regular expression pattern.

        Returns:
            Matched group of legal characters or None if there was
            no match.
        """
        # XXX: Looking at the method's docstring, wasn't the following
        #      call supposed to be `.match(val)` rather than `.search(val)`?
        match = regex.search(val)
        if match:
            return match.group(0)
        return None

    def _is_opt_primary(self):
        return self._params.get('opt.primary', False)

    def _attr_in_params(self, attr):
        """
        Check whether an attribute's name is in the request params
        and it is not empty.

        Args:
            `attr` (str): an attribute's name.

        Returns:
            True if request params contain the attribute and it is not
            empty, False otherwise.
        """
        if attr in self._params and self._params[attr]:
            return True
        return False

    def _include_in_event(self, attr):
        """
        Randomly choose whether to include an attribute in the event,
        based on the specified choice criterion.

        Args:
            `attr` (str): an attribute's name.

        Returns:
            True if the attribute should be included, False otherwise.
        """
        if attr not in self._required_attrs:
            return random.choice(self._RANDOM_CHOICE_CRITERION)
        # always return True if an attribute is on the list of required
        # attributes
        return True

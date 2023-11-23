# Copyright (c) 2013-2023 NASK. All rights reserved.

import copy
import datetime
import hashlib
import random
import re
import socket
import string
import urllib.parse
from collections.abc import (
    Iterator,
    Mapping,
)
from typing import Optional

import radar

from n6lib.class_helpers import attr_required
from n6lib.common_helpers import as_bytes
from n6lib.config import (
    ConfigError,
    ConfigMixin,
    ConfigSection,
    combined_config_spec,
)
from n6lib.const import (
    CATEGORY_ENUMS,
    CONFIDENCE_ENUMS,
    LACK_OF_IPv4_PLACEHOLDER_AS_INT,
    ORIGIN_ENUMS,
    PROTO_ENUMS,
    STATUS_ENUMS,
)
from n6lib.data_spec.typing_helpers import (
    ParamsDict,
    ResultDict,
)
from n6lib.log_helpers import get_logger
from n6lib.typing_helpers import AccessZone


LOGGER = get_logger(__name__)


class AttributeCreationError(Exception):
    """
    Exception raised when no way of creating an attribute could
    be found.
    """


class RandomEventGeneratorConfigMixin(ConfigMixin):

    # This attribute *must* be set in concrete
    # subclasses to a config section name.
    generator_config_section: str = None

    # This attribute *may* (but does not need to)
    # be extended in subclasses by overriding it
    # with another `combined_config_spec(...)`.
    config_spec_pattern = combined_config_spec('''
        [{generator_config_section}]

        possible_event_attributes :: list_of_str
        required_event_attributes :: list_of_str
        dip_categories :: list_of_str
        port_attributes :: list_of_str
        md5_attributes :: list_of_str

        possible_cc_in_address :: list_of_str
        possible_client :: list_of_str
        possible_fqdn :: list_of_str
        possible_url :: list_of_str
        possible_name :: list_of_str
        possible_source :: list_of_str
        possible_restriction :: list_of_str
        possible_target :: list_of_str

        seconds_max = 180000 :: int
        expires_days_max = 8 :: int
        random_ips_max = 5 :: int
    ''')

    @attr_required('generator_config_section', 'config_spec_pattern')
    def obtain_config(self, settings: Optional[Mapping] = None) -> ConfigSection:
        return self.get_config_section(
            settings,
            generator_config_section=self.generator_config_section)


class RandomEvent(RandomEventGeneratorConfigMixin):

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

    * By adding the attribute's name to the `port_attributes` list in
     the config, if it is a port number, or the `md5_attributes` list,
     if it is an MD5 hash value. A proper value will be returned
     for this kind of attribute.

    In last two cases, values in `_params`, if available, have
    a priority.

    If there is no method to handle the attribute, but its name
    is in `possible_event_attributes`, attribute's value still
    will be searched for in the `_params` attribute.

    By default, it is randomly chosen, based on the
    `_RANDOM_CHOICE_CRITERION`, if an attribute will be
    included in an event. To force it to be always included,
    add it to the `required_event_attributes` list in the config.
    """

    generator_config_section = 'generator_rest_api'

    _GETTER_PREFIX = '_get_'
    _POSSIBLE_VALS_PREFIX = '_possible_'
    _RANDOM_CHOICE_CRITERION = (True, True, False)
    # regexes used for a simple validation of an input data from
    # special parameters (fqdn.sub and url.sub)
    _LEGAL_FQDN_REGEX = re.compile(r'[a-zA-Z0-9.-]*', re.ASCII)
    _LEGAL_URL_REGEX = re.compile(r'[a-zA-Z0-9.-/:]*', re.ASCII)

    @classmethod
    def generate_multiple_event_data(cls,
                                     num_of_events: int,
                                     *,
                                     settings: Optional[Mapping] = None,
                                     access_zone: Optional[AccessZone] = None,
                                     client_id: Optional[str] = None,
                                     params: Optional[ParamsDict] = None,
                                     **kwargs) -> Iterator[ResultDict]:
        """
        Generate a given number of random events.

        Args/kwargs:
            `num_of_events`:
                A number of random events to generate.

        Kwargs (keyword-only):
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
            Any extra keyword arguments:
                To be passed (together with most of the above arguments)
                to the main constructor. Note that the `RandomEvent`'s
                one does *not* accept any extra keyword arguments (yet
                hypothetical subclasses may add support for some...).

        Yields:
            Generated random events (as dicts).
        """
        ready_config = cls(settings=settings).config
        for _ in range(num_of_events):
            yield cls(
                ready_config=ready_config,
                access_zone=access_zone,
                client_id=client_id,
                params=params,
                **kwargs,
            ).event

    def __init__(self, *,
                 ready_config: Optional[ConfigSection] = None,
                 settings: Optional[Mapping] = None,
                 access_zone: Optional[AccessZone] = None,
                 client_id: Optional[str] = None,
                 params: Optional[ParamsDict] = None,
                 **kwargs):
        """
        Kwargs (keyword-only):
            `ready_config` (optional; default: None):
                If not `None`, it should be ready `ConfigSection`
                mapping; then `settings` must be omitted or `None`.
            Other keyword arguments:
                See: all keyword-only arguments accepted by the
                `generate_multiple_event_data()` class method.
        """

        # (note: in the case of the `RandomEvent` class itself, the
        # `kwargs` dict needs to be empty, yet hypothetical subclasses
        # may support additional keyword arguments...)
        super().__init__(**kwargs)

        self._config_init(ready_config, settings)
        self._access_zone = access_zone
        self._client_id = client_id
        self._params = copy.deepcopy(params) if params is not None else {}
        self._min_ip = 1           # 0.0.0.1
        assert self._min_ip > LACK_OF_IPv4_PLACEHOLDER_AS_INT
        self._max_ip = 0xfffffffe  # 255.255.255.254
        self._current_datetime = datetime.datetime.utcnow()
        self._attributes_init()

    def _config_init(self,
                     ready_config: Optional[ConfigSection],
                     settings: Optional[Mapping]) -> None:

        if ready_config is not None:
            if settings is not None:
                raise TypeError('specifying both `ready_config` and `settings` is not supported')
            self.config = ready_config
        else:
            self.config = self.obtain_config(settings)

        self._possible_attrs = list(self.config['possible_event_attributes'])
        for needed_attr in ['url', 'time', 'category']:   # <- needed when creating other attrs
            self._move_attr_to_beginning_if_present(needed_attr)

        self._required_attrs = frozenset(self.config['required_event_attributes'])
        if illegal := self._required_attrs.difference(self._possible_attrs):
            listing = ', '.join(sorted(map(ascii, illegal)))
            raise ConfigError(
                f'`required_event_attributes` should be a subset of '
                f'`possible_event_attributes` (the items present in '
                f'the former and not in the latter are: {listing})')

        self._dip_categories = frozenset(self.config['dip_categories'])
        self._port_attributes = frozenset(self.config['port_attributes'])
        self._md5_attributes = frozenset(self.config['md5_attributes'])

        self._possible_cc_in_address = list(self.config['possible_cc_in_address'])
        self._possible_client = list(self.config['possible_client'])
        self._possible_fqdn = list(self.config['possible_fqdn'])
        self._possible_url = list(self.config['possible_url'])
        self._possible_name = list(self.config['possible_name'])
        self._possible_source = list(self.config['possible_source'])
        self._possible_restriction = list(self.config['possible_restriction'])
        self._possible_target = list(self.config['possible_target'])

        self._seconds_max = self.config['seconds_max']
        self._expires_days_max = self.config['expires_days_max']
        self._random_ips_max = self.config['random_ips_max']

    def _move_attr_to_beginning_if_present(self, attr):
        try:
            self._possible_attrs.remove(attr)
        except ValueError:
            pass
        else:
            self._possible_attrs.insert(0, attr)

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
                LOGGER.warning(
                    'No method of value generation could be found '
                    'for attribute %a and no values were provided '
                    'for it in request params (if any).', attr)
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
        if attr in self._port_attributes:
            return self._get_value_for_port_attr()
        if attr in self._md5_attributes:
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
                ip = self._int_to_ip(random.randint(self._min_ip, self._max_ip))
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
                    cc = random.choice(self._possible_cc_in_address)
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
            # XXX: shouldn't it be checked if `self._client_id` is not None?
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
                return self._int_to_ip(random.randint(self._min_ip, self._max_ip))
        return None

    @staticmethod
    def _get_enriched():
        # maybe TODO later: implement it in a more interesting way?
        return [[], {}]

    def _get_expires(self):
        # XXX: shouldn't it be done is such a way that: it is set only
        #      for bl events (obligatorily!) and then (and only then!)
        #      also `status` + optionally `replaces` would be set?
        max_expires = self._current_datetime + datetime.timedelta(days=self._expires_days_max)
        if self._include_in_event('expires'):
            return radar.random_datetime(self._current_datetime, max_expires)
        return None

    def _get_fqdn(self):
        # XXX: is it justified that `fqdn` is not included when `opt.primary` is set?
        if self.event['category'] in self._dip_categories or self._is_opt_primary():
            return None
        if self._attr_in_params('fqdn'):
            return random.choice(self._params['fqdn'])
        if self._attr_in_params('fqdn.sub'):
            sub = random.choice(self._params['fqdn.sub'])
            cleaned_sub = self._clean_input_value(sub, self._LEGAL_FQDN_REGEX)
            return self._get_matching_values(cleaned_sub, self._possible_fqdn)
        # XXX: is it justified that `fqdn` is not included when `opt.primary` is set?
        if self._is_opt_primary() or not self._include_in_event('fqdn'):
            return None
        if self._attr_in_params('url'):
            return self._url_to_domain(self.event['url'])
        return random.choice(self._possible_fqdn)

    def _get_modified(self):
        if self._include_in_event('modified'):
            return radar.random_datetime(self.event['time'], self._current_datetime)
        return None

    def _get_name(self):
        attr_name = 'name'
        if self._attr_in_params(attr_name):
            return random.choice(self._params[attr_name])
        if self._include_in_event(attr_name):
            return random.choice(self._possible_name)
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
        # XXX: is this logic related to `time.until` valid?
        elif self._attr_in_params('time.until'):
            time_min = self._params['time.min'][0] + hour
        else:
            time_min = self._current_datetime + delta
        if self._include_in_event('time'):
            return str(radar.random_datetime(time_min, time_max))
        return None

    def _get_url(self):
        # XXX: is it justified that `url` is not included when `opt.primary` is set?
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

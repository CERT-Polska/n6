# Copyright (c) 2022-2024 NASK. All rights reserved.

import json
from typing import Optional

from requests.exceptions import HTTPError

from n6lib.data_spec.fields import ASNFieldForN6
from n6lib.http_helpers import RequestPerformer
from n6lib.log_helpers import get_logger
from n6sdk.regexes import IPv4_CIDR_NETWORK_REGEX


LOGGER = get_logger(__name__)


class RIPEApiClient:

    """
    A simple tool to search for information about the people or
    organizations associated with a specified ASN(s) or IP network(s)
    via RIPE API.


    Optional constructor args:

      `asn_seq` (a `list` or `None`, default: `None`):
        The ASN(s) to check through the RIPE API. If not `None`,
        it should be a list containing string(s) only, which in
        addition meet(s) the following requirements:
          * consist of digits only;
          * have between 1 and 10 characters in length inclusive.

      `ip_network_seq` (a `list` or `None`, default: `None`):
        The IP network(s) to check through the RIPE API. If not
        `None`, it should be a list containing string(s) only, which
        in addition should match `IPv4_CIDR_NETWORK_REGEX` regex
        (see more: N6SDK/n6sdk/regexes.py).

      Important notice:
      the validation of the arguments presented above is simplified,
      and it does not ensure that the provided string(s) will actually
      be a valid ASN(s) or IP network(s).

    It is required to provide exactly one argument (`asn_seq` or
    `ip_network_seq`) - otherwise `ValueError` will be raised.


    Returns:
      The downloaded content, as we use to call it in the code:
      `attrs_data` (list), which is containing information about
      specified ASN(s)/IP network sequence(s).


    Exceptions raised by the constructor and/or instance interface:

      * `ValueError` -- for:
        * *none* or *both* of the arguments provided;
        * invalid (here: not passing our simplified validation)
          ASN(s) or IP network(s);
        * invalid marker passed to `_obtain_abuse_url()` method.

      * `HTTPError` -- for:
        * any exception that can be raised by the `requests`
          or `urllib3` libraries. It is important to mention
          that in some parts of the client we deliberately
          avoid throwing an `HTTPError` with the *404* status
          code.

    ***

    Typically, the client performs the following operations
    divided into three main phases:

    Phase I (initialization and validation):

      * Validates constructor's arguments - which, as we expect,
        are ASN(s) or IP network(s).

    Phase II (obtaining *unique details* URLs):

      * Creates unique URLs using each ASN/IP network,
      * Requests data from every - previously created - URL.
      * Search for `admin-c`, `tech-c` and `org` keys/values.
      * Creates unique URLs using values from `admin-c` and `tech-c`
        and `org` keys. Usually there is more than one created URL,
        but not all of them are valid.

    Phase III (obtaining *attrs_data* from *unique details URLs*
    and abuse contact finder):

      * Downloads content - as we use to call it in code, the
        `attrs_data` - from any URL created based on the data
        contained in the `admin-c`, `tech-c` and `org` keys.
        Note that not every URL is valid, in case of a 404 error
        the URL is skipped.

    ***

    Example code:
    ```
    ripe_api_client = RIPEApiClient(asn_seq=['0123456789'])
    attrs_data = ripe_api_client.run()
    ```

    ```
    ripe_api_client = RIPEApiClient(ip_network_seq=['1.1.1.1/24'])
    attrs_data = ripe_api_client.run()
    ```
    """

    ASN_URL_PATTERN = (
        'https://stat.ripe.net/data/whois/data.json?resource=as'
    )
    IP_NETWORK_URL_PATTERN = (
        'https://stat.ripe.net/data/whois/data.json?resource='
    )
    ASN_ABUSE_CONTACT_FINDER_URL_PATTERN = (
        'https://stat.ripe.net/data/abuse-contact-finder/data.json?resource=as'
    )
    IP_NETWORK_ABUSE_CONTACT_FINDER_URL_PATTERN = (
        'https://stat.ripe.net/data/abuse-contact-finder/data.json?resource='
    )

    DETAILS_ROLE_URL_PATTERN = 'https://rest.db.ripe.net/ripe/role/'
    DETAILS_PERSON_URL_PATTERN = 'https://rest.db.ripe.net/ripe/person/'
    DETAILS_ORGANISATION_URL_PATTERN = 'https://rest.db.ripe.net/ripe/organisation/'
    DETAILS_EXTENSION = '.json'
    DETAILS_UNFILTERED_EXTENSION = '?unfiltered'

    _UNIQUE_ASN_MARKER = 'ASN'
    _UNIQUE_IP_NETWORK_MARKER = 'IP Network'


    #
    # Phase I - Initialization and validation
    #

    def __init__(self,
                 asn_seq: Optional[list] = None,
                 ip_network_seq: Optional[list] = None
                 ) -> None:
        self.asn_seq = self._get_validated_as_numbers(asn_seq)
        self.ip_network_seq = self._get_validated_ip_networks(ip_network_seq)
        self.marker_to_details_urls = dict()
        if not (self.asn_seq or self.ip_network_seq):
            raise ValueError('ASN or IP Network should be provided.')
        if self.asn_seq and self.ip_network_seq:
            raise ValueError(
                'Either ASN(s) or IP Network(s) should be provided '
                '- not both of them.'
            )
        self._set_asn_and_ip_network_to_unique_details_urls_structure()

    @staticmethod
    def _get_validated_as_numbers(asn_seq: Optional[list]) -> Optional[list]:
        if asn_seq is not None:
            invalid = []
            for asn in asn_seq:
                if not (asn.isascii()
                        and asn.isdecimal()
                        and ASNFieldForN6.min_value <= int(asn) <= ASNFieldForN6.max_value):
                    invalid.append(asn)
            if invalid:
                raise ValueError(
                    f'These ASNs do not pass our validation: '
                    f'{invalid}.')
        return asn_seq

    @staticmethod
    def _get_validated_ip_networks(ip_networks_seq: Optional[list]
                                   ) -> Optional[list]:
        if ip_networks_seq is not None:
            invalid = []
            for ip_network in ip_networks_seq:
                if not IPv4_CIDR_NETWORK_REGEX.search(ip_network):
                    invalid.append(ip_networks_seq)
            if invalid:
                raise ValueError(
                    f'These IP Networks do not pass our validation: '
                    f'{invalid}.')
        return ip_networks_seq

    def _set_asn_and_ip_network_to_unique_details_urls_structure(self) -> None:
        for marker in (self._UNIQUE_ASN_MARKER, self._UNIQUE_IP_NETWORK_MARKER):
            self.marker_to_details_urls[marker] = dict()


    #
    # Phases II and III
    #

    def __call__(self):
        return self.run()

    def run(self) -> str:
        self._obtain_all_unique_details_urls(self.asn_seq, self.ip_network_seq)
        attrs_data = self._get_attrs_data_from_unique_details_urls()
        return json.dumps(attrs_data)


    # * Phase II - Obtaining unique *details* URLs:

    def _obtain_all_unique_details_urls(self,
                                        asn_seq: Optional[list] = None,
                                        ip_network_seq: Optional[list] = None
                                        ) -> None:
        if asn_seq is not None:
            self._obtain_unique_urls_from_asn_records(asn_seq)
        if ip_network_seq is not None:
            self._obtain_unique_urls_from_ip_network_records(ip_network_seq)

    def _obtain_unique_urls_from_asn_records(self, asn_seq: list) -> None:
        assert asn_seq is not None
        for asn in asn_seq:
            url = self._create_asn_request_url(asn)
            response = self._perform_single_request(url)
            self._obtain_partial_url_from_response(response=response, asn=asn)

    def _obtain_unique_urls_from_ip_network_records(self,
                                                    ip_network_seq: list
                                                    ) -> None:
        assert ip_network_seq is not None
        for ip_network in ip_network_seq:
            url = self._create_ip_network_request_url(ip_network)
            response = self._perform_single_request(url)
            self._obtain_partial_url_from_response(
                response=response,
                ip_network=ip_network
            )

    def _obtain_partial_url_from_response(self,
                                          response: dict,
                                          asn: Optional[str] = None,
                                          ip_network: Optional[str] = None,
                                          ) -> None:
        assert not (asn and ip_network)
        assert asn is not None or ip_network is not None
        if response is None:
            return None
        if response["data"]["records"]:
            for record in response["data"]["records"][0]:
                if record['key'] in ('admin-c', 'tech-c'):
                    self._provide_marker_to_unique_details_urls(
                        value=record['value'],
                        asn=asn,
                        ip_network=ip_network,
                    )
                if record['key'] == 'org':
                    self._provide_marker_to_unique_details_urls(
                        value=record['value'],
                        asn=asn,
                        ip_network=ip_network,
                        org=True,
                    )

    def _provide_marker_to_unique_details_urls(self,
                                               value: str,
                                               asn: str = None,
                                               ip_network: str = None,
                                               org: bool = False,
                                               ) -> None:
        if asn is not None:
            assert ip_network is None
            self._provide_asn_to_unique_details_urls(asn=asn,
                                                     value=value,
                                                     org=org)
        if ip_network is not None:
            assert asn is None
            self._provide_ip_network_to_unique_details_urls(ip_network=ip_network,
                                                            value=value,
                                                            org=org)

    def _provide_asn_to_unique_details_urls(self,
                                            asn: str,
                                            value: str,
                                            org: bool = False,
                                            ) -> None:
        if not self.marker_to_details_urls[self._UNIQUE_ASN_MARKER].get(asn):
            self.marker_to_details_urls[self._UNIQUE_ASN_MARKER][asn] = set()
        if org:
            self.marker_to_details_urls[self._UNIQUE_ASN_MARKER][asn].add(
                f'{self.DETAILS_ORGANISATION_URL_PATTERN}{value}{self.DETAILS_EXTENSION}{self.DETAILS_UNFILTERED_EXTENSION}'
            )
        else:
            self.marker_to_details_urls[self._UNIQUE_ASN_MARKER][asn].update((
                f'{self.DETAILS_PERSON_URL_PATTERN}{value}{self.DETAILS_EXTENSION}{self.DETAILS_UNFILTERED_EXTENSION}',
                f'{self.DETAILS_ROLE_URL_PATTERN}{value}{self.DETAILS_EXTENSION}{self.DETAILS_UNFILTERED_EXTENSION}',
            ))

    def _provide_ip_network_to_unique_details_urls(self,
                                                   ip_network: str,
                                                   value: str,
                                                   org: bool = False,
                                                   ):
        if not self.marker_to_details_urls[self._UNIQUE_IP_NETWORK_MARKER].get(ip_network):
            self.marker_to_details_urls[self._UNIQUE_IP_NETWORK_MARKER][ip_network] = set()
        if org:
            self.marker_to_details_urls[self._UNIQUE_IP_NETWORK_MARKER][ip_network].add(
                f'{self.DETAILS_ORGANISATION_URL_PATTERN}{value}{self.DETAILS_EXTENSION}{self.DETAILS_UNFILTERED_EXTENSION}'
            )
        else:
            self.marker_to_details_urls[self._UNIQUE_IP_NETWORK_MARKER][ip_network].update((
                f'{self.DETAILS_PERSON_URL_PATTERN}{value}{self.DETAILS_EXTENSION}{self.DETAILS_UNFILTERED_EXTENSION}',
                f'{self.DETAILS_ROLE_URL_PATTERN}{value}{self.DETAILS_EXTENSION}{self.DETAILS_UNFILTERED_EXTENSION}',
            ))


    # * Phase III - Obtaining data from unique *details* URLs + abuse contact finder:

    def _get_attrs_data_from_unique_details_urls(self) -> list:
        attrs_data_from_details_urls = []
        for (marker, asn_or_ip_network_to_urls) in self.marker_to_details_urls.items():
            if asn_or_ip_network_to_urls:
                self._provide_attrs_data(attrs_data_from_details_urls,
                                         marker,
                                         asn_or_ip_network_to_urls)
        return attrs_data_from_details_urls

    def _provide_attrs_data(self,
                            attrs_data_from_details_urls: list,
                            marker: str,
                            asn_or_ip_network_to_urls: dict,
                            ) -> None:
        for asn_or_ip_network, unique_urls in asn_or_ip_network_to_urls.items():
            adjusted_attributes = [('Unfiltered data for', str(asn_or_ip_network))]
            contact_url = self._obtain_abuse_url(asn_or_ip_network, marker)
            response = self._perform_single_request(contact_url)
            abuse_contact_emails = response['data']['abuse_contacts']
            adjusted_attributes.append(
                ('Abuse Contact Emails', abuse_contact_emails)
            )
            for url in unique_urls:
                attrs = self._perform_single_request(url)
                if attrs:
                    for attr_obj in attrs["objects"]["object"]:
                        for attr in attr_obj['attributes']['attribute']:
                            adjusted_attributes.append(
                                (attr['name'], attr['value'])
                            )
                    adjusted_attributes.append(('', ''))
            attrs_data_from_details_urls.append(adjusted_attributes)

    def _obtain_abuse_url(self, asn_or_ip_network: str, marker: str) -> str:
        if marker == self._UNIQUE_ASN_MARKER:
            contact_url = self._create_asn_abuse_contact_finder_url(
                asn_or_ip_network)
        elif marker == self._UNIQUE_IP_NETWORK_MARKER:
            contact_url = self._create_ip_network_abuse_contact_finder_url(
                asn_or_ip_network)
        else:
            raise ValueError(
                f'Invalid marker {marker}. '
                f'Allowed markers: '
                f'{self._UNIQUE_ASN_MARKER}, '
                f'{self._UNIQUE_IP_NETWORK_MARKER}.')
        return contact_url


    #
    # Helpers
    #

    def _create_asn_request_url(self, asn: str) -> str:
        assert asn is not None
        return f'{self.ASN_URL_PATTERN}{asn}'

    def _create_ip_network_request_url(self, ip_network: str) -> str:
        assert ip_network is not None
        return f'{self.IP_NETWORK_URL_PATTERN}{ip_network}'

    def _create_asn_abuse_contact_finder_url(self, asn: str) -> str:
        assert asn is not None
        return f'{self.ASN_ABUSE_CONTACT_FINDER_URL_PATTERN}{asn}'

    def _create_ip_network_abuse_contact_finder_url(self,
                                                    ip_network: str) -> str:
        assert ip_network is not None
        return f'{self.IP_NETWORK_ABUSE_CONTACT_FINDER_URL_PATTERN}{ip_network}'

    @staticmethod
    def _perform_single_request(url: str) -> Optional[dict]:
        try:
            with RequestPerformer('GET', url) as perf:
                return json.loads(perf.response.content)
        except HTTPError as e:
            if e.response.status_code == 404:
                return None
            LOGGER.warning(e)
            raise e

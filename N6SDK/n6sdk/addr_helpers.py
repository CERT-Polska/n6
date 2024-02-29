# Copyright (c) 2013-2023 NASK. All rights reserved.

import bisect
import logging
import socket
from collections.abc import Sequence
from ipaddress import (
    collapse_addresses,
    IPv4Address,
    IPv4Network,
)
from typing import Union


LOGGER = logging.getLogger(__name__)


def ip_network_as_tuple(ip_network_str: str) -> tuple[str, int]:
    """
    >>> ip_network_as_tuple('10.20.30.40/24')
    ('10.20.30.40', 24)
    """
    ip_str, prefixlen_str = ip_network_str.split("/")
    prefixlen = int(prefixlen_str)
    return ip_str, prefixlen


def ip_network_tuple_to_min_max_ip(ip_network_tuple: tuple[str, int],
                                   *,
                                   force_min_ip_greater_than_zero: bool = False,
                                   ) -> tuple[int, int]:
    """
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.0', 24))
    (169090560, 169090815)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 24))
    (169090560, 169090815)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 32))
    (169090601, 169090601)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 0))
    (0, 4294967295)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.0', 0))
    (0, 4294967295)
    >>> ip_network_tuple_to_min_max_ip(('255.255.255.255', 0))
    (0, 4294967295)
    >>> ip_network_tuple_to_min_max_ip(('0.0.2.0', 24))
    (512, 767)
    >>> ip_network_tuple_to_min_max_ip(('0.0.1.0', 24))
    (256, 511)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.0', 24))
    (0, 255)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.2', 32))
    (2, 2)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.1', 32))
    (1, 1)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.0', 32))
    (0, 0)

    >>> ip_network_tuple_to_min_max_ip(('10.20.30.0', 24),
    ...                                force_min_ip_greater_than_zero=True)
    (169090560, 169090815)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 24),
    ...                                force_min_ip_greater_than_zero=True)
    (169090560, 169090815)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 32),
    ...                                force_min_ip_greater_than_zero=True)
    (169090601, 169090601)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 0),
    ...                                force_min_ip_greater_than_zero=True)   # min IP forced to 1
    (1, 4294967295)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.0', 0),
    ...                                force_min_ip_greater_than_zero=True)   # min IP forced to 1
    (1, 4294967295)
    >>> ip_network_tuple_to_min_max_ip(('255.255.255.255', 0),
    ...                                force_min_ip_greater_than_zero=True)   # min IP forced to 1
    (1, 4294967295)
    >>> ip_network_tuple_to_min_max_ip(('0.0.2.0', 24),
    ...                                force_min_ip_greater_than_zero=True)
    (512, 767)
    >>> ip_network_tuple_to_min_max_ip(('0.0.1.0', 24),
    ...                                force_min_ip_greater_than_zero=True)
    (256, 511)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.0', 24),
    ...                                force_min_ip_greater_than_zero=True)   # min IP forced to 1
    (1, 255)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.2', 32),
    ...                                force_min_ip_greater_than_zero=True)
    (2, 2)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.1', 32),
    ...                                force_min_ip_greater_than_zero=True)
    (1, 1)
    >>> ip_network_tuple_to_min_max_ip(('0.0.0.0', 32),
    ...                                force_min_ip_greater_than_zero=True)   # min IP forced to 1
    (1, 0)
    """
    ip_str, prefixlen = ip_network_tuple
    ip_int = ip_str_to_int(ip_str)
    min_ip = (((1 << prefixlen) - 1) << (32 - prefixlen)) & ip_int
    if force_min_ip_greater_than_zero and min_ip <= 0:
        min_ip = 1
    max_ip = (((1 << (32 - prefixlen)) - 1)) | ip_int
    return min_ip, max_ip


def ip_str_to_int(ip_str: str) -> int:
    """
    >>> ip_str_to_int('10.20.30.41')
    169090601
    >>> ip_str_to_int('0.0.0.0')
    0
    >>> ip_str_to_int('255.255.255.255')
    4294967295
    >>> ip_str_to_int('126.127.128.129')
    2122285185
    """
    return int.from_bytes(socket.inet_aton(ip_str), 'big')


def ip_int_to_str(ip_int: int) -> str:
    """
    >>> ip_int_to_str(169090601)
    '10.20.30.41'
    >>> ip_int_to_str(0)
    '0.0.0.0'
    >>> ip_int_to_str(4294967295)
    '255.255.255.255'
    >>> ip_int_to_str(2122285185)
    '126.127.128.129'
    """
    return socket.inet_ntoa(ip_int.to_bytes(4, 'big'))


IPv4AddressOrNetworkDescription = Union[
    IPv4Address,
    IPv4Network,
    str,    # address or network
    int,    # address
    bytes,  # address
    tuple[
        Union[IPv4Address, str, int, bytes],  # 1st item: address
        Union[int, str],                      # 2nd item: prefix mask
    ],
]


class IPv4Container:
    """
    A container for IPv4 addresses.

    Instances of this class support the following operations:

    * efficient *membership test*, i.e., support for the `in` operator,
      to check whether an `IPv4Container` instance contains a particular
      IP address (see the docs of the method `__contains__()`);

    * *logical truth test*, i.e., support for `if` tests (and `bool`
      calls, etc.), to check whether an `IPv4Container` instance
      contains *at least one* IP address (see the docs of the method
      `__bool__()`);

    The class provides also a read-only property: `networks` -- a
    sorted sequence of `IPv4Network` instances covering all contained
    IP addresses (see its docs).

    Constructor args:
        Each of them should be one of:
            - an `ipaddress.IPv4Network` instance,
            - an `ipaddress.IPv4Address` instance,
            - an IPv4 address as a `str`, `int` or an integer number
              packed into `bytes` (big-endian), or an IPv4 network as
              a `str` or a two-tuple containing an IPv4 address and a
              prefix/mask (i.e., whatever is accepted by the constructor
              `ipaddress.IPv4Network`).

    Constructor-raised exceptions:
        `ipaddress.IPv4Network`-constructor-related exceptions.

    *Note:* `IPv4Container` -- like `ipaddress.IPv4Network` (when called
    without `strict=False`) and unlike most of *n6*'s code related to IP
    networks -- requires that addresses in IP network specifications do
    *not* have host bits set (e.g., `1.2.3.0/24` is OK, but `1.2.3.4/24`
    is not).
    """

    def __init__(self, *ip_or_network_seq: IPv4AddressOrNetworkDescription) -> None:
        self._networks = self._prepare_networks(ip_or_network_seq)
        self._search_sequence = self._prepare_search_sequence(self._networks)

    @property
    def networks(self) -> Sequence[IPv4Network]:
        r"""
        An immutable sequence of `ipaddress.IPv4Network` objects which
        cover all IP addresses this `IPv4Container` instance contains.
        The networks are already *sorted* and *collapsed* (there are
        *no duplicates* and *no overlapping networks*).

        >>> from collections.abc import Sequence, MutableSequence
        >>> isinstance(IPv4Container('1.1.1.1').networks, Sequence)
        True
        >>> isinstance(IPv4Container('1.1.1.1').networks, MutableSequence)
        False

        >>> list(IPv4Container('1.1.1.1').networks)
        [IPv4Network('1.1.1.1/32')]
        >>> list(IPv4Container('1.1.1.1/32').networks)
        [IPv4Network('1.1.1.1/32')]
        >>> list(IPv4Container('1.1.1.1', '1.1.1.1').networks)
        [IPv4Network('1.1.1.1/32')]
        >>> list(IPv4Container('1.1.1.1', '1.1.1.1/32').networks)
        [IPv4Network('1.1.1.1/32')]
        >>> list(IPv4Container('1.1.1.1/32', '1.1.1.1/32', '1.1.1.1/32').networks)
        [IPv4Network('1.1.1.1/32')]
        >>> list(IPv4Container('1.1.1.1', '1.1.1.1/32', '1.1.1.1', '1.1.1.1/32').networks)
        [IPv4Network('1.1.1.1/32')]

        >>> list(IPv4Container('7.7.7.7', '1.1.1.0/24').networks)
        [IPv4Network('1.1.1.0/24'), IPv4Network('7.7.7.7/32')]
        >>> list(IPv4Container('7.7.7.7/32', '1.1.1.0/24').networks)
        [IPv4Network('1.1.1.0/24'), IPv4Network('7.7.7.7/32')]
        >>> list(IPv4Container('7.7.7.7/32', '7.7.7.7', '1.1.1.0/24').networks)
        [IPv4Network('1.1.1.0/24'), IPv4Network('7.7.7.7/32')]

        >>> list(IPv4Container('2.0.0.0/16', '6.6.0.0/16').networks)
        [IPv4Network('2.0.0.0/16'), IPv4Network('6.6.0.0/16')]
        >>> list(IPv4Container('6.6.0.0/16', '2.0.0.0/16').networks)
        [IPv4Network('2.0.0.0/16'), IPv4Network('6.6.0.0/16')]
        >>> list(IPv4Container('6.6.0.0/16', '2.0.0.0/16', '6.6.123.234').networks)
        [IPv4Network('2.0.0.0/16'), IPv4Network('6.6.0.0/16')]

        >>> list(IPv4Container('1.1.1.0/24', '1.1.0.0/24').networks)
        [IPv4Network('1.1.0.0/23')]
        >>> list(IPv4Container('1.1.0.0/23').networks)
        [IPv4Network('1.1.0.0/23')]
        >>> list(IPv4Container('1.1.0.0/23', '1.1.0.0/23').networks)
        [IPv4Network('1.1.0.0/23')]

        >>> list(IPv4Container('1.1.1.1', '1.1.1.0').networks)
        [IPv4Network('1.1.1.0/31')]
        >>> list(IPv4Container('1.1.1.1', '1.1.1.0/32').networks)
        [IPv4Network('1.1.1.0/31')]
        >>> list(IPv4Container('1.1.1.1/32', '1.1.1.0').networks)
        [IPv4Network('1.1.1.0/31')]
        >>> list(IPv4Container('1.1.1.1/32', '1.1.1.0/32').networks)
        [IPv4Network('1.1.1.0/31')]

        >>> list(IPv4Container(                                    # doctest: +NORMALIZE_WHITESPACE
        ...     # (contains all addresses from the `10.10.10.0/24` network
        ...     # *except* `10.10.10.152`)
        ...     '10.10.10.154/31',
        ...     '10.10.10.0/25',
        ...     '10.10.10.156/30',
        ...     '10.10.10.128/28',
        ...     '10.10.10.192/26',
        ...     '10.10.10.144/29',
        ...     '10.10.10.160/27',
        ...     '10.10.10.153/32',
        ... ).networks)
        [IPv4Network('10.10.10.0/25'), IPv4Network('10.10.10.128/28'),
         IPv4Network('10.10.10.144/29'), IPv4Network('10.10.10.153/32'),
         IPv4Network('10.10.10.154/31'), IPv4Network('10.10.10.156/30'),
         IPv4Network('10.10.10.160/27'), IPv4Network('10.10.10.192/26')]

        >>> list(IPv4Container('10.10.10.0/24').networks)
        [IPv4Network('10.10.10.0/24')]
        >>> list(IPv4Container(
        ...     # (contains all addresses from the `10.10.10.0/24` network
        ...     # *including* `10.10.10.152` => to be merged...)
        ...     '10.10.10.152/32',
        ...     '10.10.10.154/31',
        ...     '10.10.10.0/25',
        ...     '10.10.10.156/30',
        ...     '10.10.10.128/28',
        ...     '10.10.10.192/26',
        ...     '10.10.10.144/29',
        ...     '10.10.10.160/27',
        ...     '10.10.10.153/32',
        ... ).networks)
        [IPv4Network('10.10.10.0/24')]
        >>> list(IPv4Container(
        ...     '10.10.10.152/32',
        ...     '10.10.10.154/31',
        ...     '10.10.10.0/25',
        ...     '10.10.10.156/30',
        ...     '10.10.10.128/28',
        ...     '10.10.10.0/24',     # <- Note: this one contains all others...
        ...     '10.10.10.192/26',
        ...     '10.10.10.144/29',
        ...     '10.10.10.160/27',
        ...     '10.10.10.153/32',
        ... ).networks)
        [IPv4Network('10.10.10.0/24')]
        >>> list(IPv4Container(      # (same as previous except that without '10.10.10.152/32')
        ...     '10.10.10.154/31',
        ...     '10.10.10.0/25',
        ...     '10.10.10.156/30',
        ...     '10.10.10.128/28',
        ...     '10.10.10.0/24',     # <- Note: this one contains all others + '10.10.10.152/32'
        ...     '10.10.10.192/26',
        ...     '10.10.10.144/29',
        ...     '10.10.10.160/27',
        ...     '10.10.10.153/32',
        ... ).networks)
        [IPv4Network('10.10.10.0/24')]
        >>> list(IPv4Container(
        ...     '10.10.8.0/21',      # <- Note: this one contains all others + much more...
        ...     '10.10.10.154/31',
        ...     '10.10.10.0/25',
        ...     '10.10.10.156/30',
        ...     '10.10.10.128/28',
        ...     '10.10.10.192/26',
        ...     '10.10.10.144/29',
        ...     '10.10.10.160/27',
        ...     '10.10.10.153/32',
        ... ).networks)
        [IPv4Network('10.10.8.0/21')]

        >>> another = IPv4Container(
        ...     '100.200.80.160/31',
        ...     '10.20.30.42/31',
        ...     '0.0.0.0/29',
        ...     '200.200.200.201',
        ...     '1.2.3.4',
        ...     '255.255.255.252/30',
        ...     '10.20.30.42/31',      # (ignored duplicates...)
        ...     '255.255.255.254/31',  # (ignored duplicates...)
        ...     '1.2.3.4/32',          # (ignored duplicate...)
        ...     '200.200.200.201',     # (ignored duplicate...)
        ...     '10.20.30.40/32',
        ...     '192.168.123.16/30',
        ...     '200.200.200.200',
        ... )
        >>> list(another.networks)                                 # doctest: +NORMALIZE_WHITESPACE
        [IPv4Network('0.0.0.0/29'), IPv4Network('1.2.3.4/32'),
         IPv4Network('10.20.30.40/32'), IPv4Network('10.20.30.42/31'),
         IPv4Network('100.200.80.160/31'), IPv4Network('192.168.123.16/30'),
         IPv4Network('200.200.200.200/31'), IPv4Network('255.255.255.252/30')]

        Note that, because the items of `networks` are instances of
        `ipaddress.IPv4Network`, you can easily obtain other useful
        data. For example, to iterate over all contained IP addresses,
        you can use the `itertools.chain.from_iterable()` helper or
        just a "flattening" comprehension:

        >>> from itertools import chain
        >>> list(chain.from_iterable(another.networks))            # doctest: +NORMALIZE_WHITESPACE
        [IPv4Address('0.0.0.0'), IPv4Address('0.0.0.1'),
         IPv4Address('0.0.0.2'), IPv4Address('0.0.0.3'),
         IPv4Address('0.0.0.4'), IPv4Address('0.0.0.5'),
         IPv4Address('0.0.0.6'), IPv4Address('0.0.0.7'),
         IPv4Address('1.2.3.4'), IPv4Address('10.20.30.40'),
         IPv4Address('10.20.30.42'), IPv4Address('10.20.30.43'),
         IPv4Address('100.200.80.160'), IPv4Address('100.200.80.161'),
         IPv4Address('192.168.123.16'), IPv4Address('192.168.123.17'),
         IPv4Address('192.168.123.18'), IPv4Address('192.168.123.19'),
         IPv4Address('200.200.200.200'), IPv4Address('200.200.200.201'),
         IPv4Address('255.255.255.252'), IPv4Address('255.255.255.253'),
         IPv4Address('255.255.255.254'), IPv4Address('255.255.255.255')]

        >>> [str(ip) for net in another.networks for ip in net]    # doctest: +NORMALIZE_WHITESPACE
        ['0.0.0.0', '0.0.0.1',
         '0.0.0.2', '0.0.0.3',
         '0.0.0.4', '0.0.0.5',
         '0.0.0.6', '0.0.0.7',
         '1.2.3.4', '10.20.30.40',
         '10.20.30.42', '10.20.30.43',
         '100.200.80.160', '100.200.80.161',
         '192.168.123.16', '192.168.123.17',
         '192.168.123.18', '192.168.123.19',
         '200.200.200.200', '200.200.200.201',
         '255.255.255.252', '255.255.255.253',
         '255.255.255.254', '255.255.255.255']
        """
        return self._networks

    def __contains__(self, ip: Union[IPv4Address, str, int, bytes]) -> bool:
        r"""
        Whether this `IPv4Container` contains the given IP address.

        The argument have to be an IPv4 address, provided as one of:

            - an `ipaddress.IPv4Address` instance,
            - a `str`,
            - an `int`,
            - an integer number packed into a `bytes` object of length 4,
              with the most significant octet first (big-endian);

        that is, either an `ipaddress.IPv4Address` or any object
        acceptable by the `ipaddress.IPv4Address` constructor.

        Raises:
            `ipaddress.IPv4Address`-constructor-related exceptions.

        *Note:* the computational complexity of this search operation
        is logarithmic, i.e., `O(log n)` (where `n` is derived from
        the number of IP networks that are provided by the `networks`
        property). Therefore, even a big number of networks is searched
        through very quickly.

        >>> ips = IPv4Container('1.1.1.1')
        >>> IPv4Address('1.1.1.0') in ips
        False
        >>> IPv4Address('1.1.1.1') in ips
        True
        >>> IPv4Address('1.1.1.2') in ips
        False
        >>> IPv4Address('0.0.0.0') in ips
        False
        >>> IPv4Address('0.0.0.1') in ips
        False
        >>> IPv4Address('0.1.1.1') in ips
        False
        >>> IPv4Address('1.1.0.0') in ips
        False
        >>> IPv4Address('1.1.0.255') in ips
        False
        >>> IPv4Address('1.1.1.0') in ips
        False
        >>> IPv4Address('1.1.1.3') in ips
        False
        >>> IPv4Address('1.1.1.128') in ips
        False
        >>> IPv4Address('1.1.1.255') in ips
        False
        >>> IPv4Address('2.2.2.2') in ips
        False
        >>> IPv4Address('255.255.255.255') in ips
        False
        >>> '1.1.1.0' in ips
        False
        >>> '1.1.1.1' in ips
        True
        >>> '1.1.1.2' in ips
        False
        >>> 16843008 in ips
        False
        >>> 16843009 in ips
        True
        >>> 16843010 in ips
        False
        >>> 2 in ips
        False
        >>> b'\x01\x01\x01\x00' in ips
        False
        >>> b'\x01\x01\x01\x01' in ips
        True
        >>> b'\x01\x01\x01\x02' in ips
        False
        >>> b'\x01\x01\x01\x03' in ips
        False

        >>> ips2 = IPv4Container('7.7.7.7', '1.1.1.0/24')
        >>> IPv4Address('1.1.1.2') in ips2
        True
        >>> IPv4Address('8.8.8.8') in ips2
        False
        >>> '0.0.0.0' in ips2
        False
        >>> '0.1.1.1' in ips2
        False
        >>> '1.1.0.0' in ips2
        False
        >>> '1.1.0.254' in ips2
        False
        >>> '1.1.0.255' in ips2
        False
        >>> '1.1.1.0' in ips2
        True
        >>> '1.1.1.1' in ips2
        True
        >>> '1.1.1.2' in ips2
        True
        >>> '1.1.1.6' in ips2
        True
        >>> '1.1.1.128' in ips2
        True
        >>> '1.1.1.254' in ips2
        True
        >>> '1.1.1.255' in ips2
        True
        >>> '1.1.2.0' in ips2
        False
        >>> '1.1.2.1' in ips2
        False
        >>> '1.1.2.2' in ips2
        False
        >>> '2.2.2.2' in ips2
        False
        >>> '6.7.7.7' in ips2
        False
        >>> '7.7.7.6' in ips2
        False
        >>> '7.7.7.7' in ips2
        True
        >>> '7.7.7.8' in ips2
        False
        >>> '8.7.7.6' in ips2
        False
        >>> '255.255.255.255' in ips2
        False
        >>> 16843010 in ips2
        True
        >>> 67372036 in ips2
        False
        >>> b'\x01\x01\x01\x01' in ips2
        True
        >>> b'\x03\x03\x03\x03' in ips2
        False

        >>> ips3 = IPv4Container('2.0.0.0/16', '6.6.0.0/16')
        >>> IPv4Address('1.255.255.255') in ips3
        False
        >>> IPv4Address('2.0.0.0') in ips3
        True
        >>> IPv4Address('2.0.1.2') in ips3
        True
        >>> IPv4Address('2.0.255.255') in ips3
        True
        >>> IPv4Address('2.1.0.0') in ips3
        False
        >>> IPv4Address('6.5.4.3') in ips3
        False
        >>> IPv4Address('6.5.255.255') in ips3
        False
        >>> IPv4Address('6.6.0.0') in ips3
        True
        >>> IPv4Address('6.6.0.128') in ips3
        True
        >>> IPv4Address('6.6.0.255') in ips3
        True
        >>> IPv4Address('6.6.1.0') in ips3
        True
        >>> IPv4Address('6.6.255.255') in ips3
        True
        >>> IPv4Address('6.7.0.0') in ips3
        False
        >>> IPv4Address('6.255.255.255') in ips3
        False
        >>> IPv4Address('6.0.0.0') in ips3
        False
        >>> '2.0.1.2' in ips3
        True
        >>> '6.5.4.3' in ips3
        False
        >>> 33555461 in ips3
        True
        >>> 84215045 in ips3
        False
        >>> b'\x06\x06\x08\x08' in ips3
        True
        >>> b'\x08\x08\x08\x08' in ips3
        False

        >>> ips4 = IPv4Container(
        ...     # (contains all addresses from the `10.10.10.0/24` network
        ...     # *except* `10.10.10.152`)
        ...     '10.10.10.0/25',
        ...     '10.10.10.128/28',
        ...     '10.10.10.144/29',
        ...     '10.10.10.153/32',
        ...     '10.10.10.154/31',
        ...     '10.10.10.156/30',
        ...     '10.10.10.160/27',
        ...     '10.10.10.192/26',
        ... )
        >>> '10.10.9.255' in ips4
        False
        >>> all(f'10.10.10.{i}' in ips4
        ...     for i in range(0, 152))
        True
        >>> '10.10.10.152' in ips4
        False
        >>> all(f'10.10.10.{i}' in ips4
        ...     for i in range(153, 256))
        True
        >>> '10.10.11.0' in ips4
        False

        >>> ips5 = IPv4Container(
        ...     '200.200.200.201',
        ...     '255.255.255.252/30',
        ...     '1.2.3.4',
        ...     '10.20.30.42/31',
        ...     '0.0.0.0/29',
        ...     '192.168.123.16/30',
        ...     '200.200.200.200',
        ...     '10.20.30.40/32',
        ...     '100.200.80.160/31',
        ... )
        >>> IPv4Address(0) in ips5
        True
        >>> '0.0.0.1' in ips5
        True
        >>> 2 in ips5
        True
        >>> b'\x00\x00\x00\x03' in ips5
        True
        >>> 7 in ips5
        True
        >>> 8 in ips5
        False
        >>> b'\x01\x02\x03\x03' in ips5
        False
        >>> b'\x01\x02\x03\x04' in ips5
        True
        >>> b'\x01\x02\x03\x05' in ips5
        False
        >>> '10.20.30.39' in ips5
        False
        >>> '10.20.30.40' in ips5
        True
        >>> '10.20.30.41' in ips5
        False
        >>> '10.20.30.42' in ips5
        True
        >>> '10.20.30.43' in ips5
        True
        >>> '10.20.30.44' in ips5
        False
        >>> IPv4Address('100.200.80.159') in ips5
        False
        >>> IPv4Address('100.200.80.160') in ips5
        True
        >>> IPv4Address('100.200.80.161') in ips5
        True
        >>> IPv4Address('100.200.80.162') in ips5
        False
        >>> ip_str_to_int('192.168.123.15') in ips5
        False
        >>> ip_str_to_int('192.168.123.16') in ips5
        True
        >>> ip_str_to_int('192.168.123.17') in ips5
        True
        >>> ip_str_to_int('192.168.123.18') in ips5
        True
        >>> ip_str_to_int('192.168.123.19') in ips5
        True
        >>> ip_str_to_int('192.168.123.20') in ips5
        False
        >>> '200.200.200.199' in ips5
        False
        >>> '200.200.200.200' in ips5
        True
        >>> '200.200.200.201' in ips5
        True
        >>> '200.200.200.202' in ips5
        False
        >>> ip_str_to_int('255.255.255.251').to_bytes(4, 'big') in ips5
        False
        >>> ip_str_to_int('255.255.255.252').to_bytes(4, 'big') in ips5
        True
        >>> ip_str_to_int('255.255.255.253').to_bytes(4, 'big') in ips5
        True
        >>> ip_str_to_int('255.255.255.254').to_bytes(4, 'big') in ips5
        True
        >>> ip_str_to_int('255.255.255.255').to_bytes(4, 'big') in ips5
        True

        >>> '1.1.1' in ips5                                     # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> '1.1.1.1.1' in ips5                                 # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> -1 in ips5                                          # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> (2 ** 32) in ips5                                   # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> b'\x00\x00\x03' in ips5                             # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> b'\x00\x00\x03\x03\x03' in ips5                     # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> 1.1 in ips5                                         # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> [123] in ips5                                       # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...

        >>> None in ips5                                        # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          ...
        ipaddress.AddressValueError: ...
        """
        if not isinstance(ip, IPv4Address):
            ip = IPv4Address(ip)
        return self._contains_int(int(ip))

    def __bool__(self) -> bool:
        r"""
        Whether this `IPv4Container` contains *at least one address*.

        >>> bool(IPv4Container())
        False
        >>> bool(IPv4Container('7.7.7.7'))
        True
        >>> bool(IPv4Container('1.1.1.0/24'))
        True
        >>> bool(IPv4Container('7.7.7.7', '1.1.1.0/24'))
        True
        """
        return bool(self._networks)

    def __repr__(self) -> str:
        r"""
        >>> IPv4Container('1.1.1.1')
        IPv4Container('1.1.1.1/32')
        >>> IPv4Container(b'\x07\x07\x07\x07', IPv4Network('1.1.1.0/24'))
        IPv4Container('1.1.1.0/24', '7.7.7.7/32')
        >>> IPv4Container('2.0.0.0/16', '3.3.3.0/24', '10.20.128.0/20', '1.1.1.1')
        IPv4Container('1.1.1.1/32', '2.0.0.0/16', '3.3.3.0/24', '10.20.128.0/20')
        >>> IPv4Container('2.0.0.0/16', '6.6.0.0/16',
        ...               '3.3.3.0/24', '10.20.128.0/20', '1.1.1.1')
        IPv4Container('1.1.1.1/32', '2.0.0.0/16', '3.3.3.0/24', '6.6.0.0/16', <...and 1 more...>)
        >>> IPv4Container('2.0.0.0/16', '6.6.0.0/16', '5.4.3.2/31', '255.255.255.255',
        ...               '3.3.3.0/24', '10.20.128.0/20', '1.1.1.1', '192.168.0.1/32')
        IPv4Container('1.1.1.1/32', '2.0.0.0/16', '3.3.3.0/24', '5.4.3.2/31', <...and 4 more...>)
        """
        limit = self._REPR_NETWORKS_LIMIT
        content_repr = ', '.join(repr(str(net)) for net in self._networks[:limit])
        if len(self._networks) > limit:
            content_repr += f', <...and {len(self._networks) - limit} more...>'
        return f"{type(self).__qualname__}({content_repr})"

    #
    # Internal helpers

    _REPR_NETWORKS_LIMIT = 4

    @classmethod
    def _prepare_networks(cls,
                          ip_or_network_seq: Sequence[IPv4AddressOrNetworkDescription],
                          ) -> tuple[IPv4Network, ...]:
        """
        Internal helper invoked in `__init__()` -- to compute the
        `_networks` internal attribute's value, to be (in particular)
        exposed as the `networks` public property (see its docs...).
        """
        uncollapsed_networks = map(cls._convert_to_network, ip_or_network_seq)
        networks = tuple(collapse_addresses(uncollapsed_networks))
        if __debug__:
            endpoints = [ip for net in networks for ip in (
                [net.network_address] if net.prefixlen == net.max_prefixlen
                else [net.network_address, net.broadcast_address])]
            assert endpoints == sorted(set(endpoints))
        return networks

    @staticmethod
    def _convert_to_network(ip_or_network: IPv4AddressOrNetworkDescription) -> IPv4Network:
        r"""
        Internal helper: convert an address or a network (in any form
        accepted by the class constructor -- see the description of the
        constructor...) to an `ipaddress.IPv4Network` object.

        >>> a = IPv4Container()
        >>> a._convert_to_network(IPv4Address('6.6.0.0'))
        IPv4Network('6.6.0.0/32')
        >>> a._convert_to_network((IPv4Address('6.6.0.0'), 16))
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network(IPv4Network('6.6.0.0/16'))
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network('6.6.0.0')
        IPv4Network('6.6.0.0/32')
        >>> a._convert_to_network(('6.6.0.0', 16))
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network('6.6.0.0/16')
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network('6.6.0.0/255.255.0.0')
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network('6.6.0.0/0.0.255.255')
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network(('6.6.0.0', '255.255.0.0'))
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network(('6.6.0.0', '0.0.255.255'))
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network(101056512)
        IPv4Network('6.6.0.0/32')
        >>> a._convert_to_network((101056512, 16))
        IPv4Network('6.6.0.0/16')
        >>> a._convert_to_network(b'\x06\x06\x00\x00')
        IPv4Network('6.6.0.0/32')
        >>> a._convert_to_network((b'\x06\x06\x00\x00', 16))
        IPv4Network('6.6.0.0/16')
        """
        if isinstance(ip_or_network, IPv4Network):
            return ip_or_network
        elif isinstance(ip_or_network, IPv4Address):
            return IPv4Network(str(ip_or_network))
        else:
            return IPv4Network(ip_or_network)

    @staticmethod
    def _prepare_search_sequence(networks: tuple[IPv4Network, ...]) -> tuple[int, ...]:
        r"""
        Internal helper invoked in `__init__()` -- to compute the
        `_search_sequence` internal attribute's value.

        Based on the given sequence of networks (already sorted and
        collapsed, see the docs of the `networks` public property...),
        prepare an internal *search sequence* -- which is a strictly
        increasing sequence of `int` values that represent, alternately,
        *lower endpoint* and *upper endpoint plus one* of consecutive
        non-overlapping and non-adjacent IP intervals (as adjacent ones
        are automatically merged).

        The sequence has such a nice property that applying to it the
        `bisect_right()` function from the stdlib `bisect` module,
        with the second argument set to an `int` representing an IP
        being searched, always returns:

        * an *odd* value if the `IPv4Container` instance contains the IP,
        * an *even* value if the `IPv4Container` instance does not contain
          the IP

        (see the internal method `_contains_int()`).

        >>> a = IPv4Container()
        >>> a._networks
        ()
        >>> a._search_sequence
        ()
        >>> a._contains_int(0)
        False
        >>> a._contains_int(1)
        False
        >>> a._contains_int(2)
        False
        >>> a._contains_int(4294967295)
        False
        >>> a._contains_int(4294967296)  # (impossible case, as not in IPv4 range...)
        False
        >>> a._contains_int(-1)          # (impossible case, as not in IPv4 range...)
        False

        >>> b = IPv4Container('0.0.0.7')
        >>> b._networks
        (IPv4Network('0.0.0.7/32'),)
        >>> b._search_sequence
        (7, 8)
        >>> b._contains_int(0)
        False
        >>> b._contains_int(1)
        False
        >>> b._contains_int(2)
        False
        >>> b._contains_int(6)
        False
        >>> b._contains_int(7)
        True
        >>> b._contains_int(8)
        False
        >>> b._contains_int(4294967295)
        False
        >>> b._contains_int(4294967296)  # (impossible case, as not in IPv4 range...)
        False
        >>> b._contains_int(-1)          # (impossible case, as not in IPv4 range...)
        False

        >>> c = IPv4Container('0.0.1.0/24', '0.0.0.7')
        >>> c._networks
        (IPv4Network('0.0.0.7/32'), IPv4Network('0.0.1.0/24'))
        >>> c._search_sequence
        (7, 8, 256, 512)
        >>> c._contains_int(0)
        False
        >>> c._contains_int(1)
        False
        >>> c._contains_int(2)
        False
        >>> c._contains_int(6)
        False
        >>> c._contains_int(7)
        True
        >>> c._contains_int(8)
        False
        >>> c._contains_int(255)
        False
        >>> c._contains_int(256)
        True
        >>> c._contains_int(257)
        True
        >>> c._contains_int(383)
        True
        >>> c._contains_int(384)
        True
        >>> c._contains_int(511)
        True
        >>> c._contains_int(512)
        False
        >>> c._contains_int(4294967295)
        False
        >>> c._contains_int(4294967296)  # (impossible case, as not in IPv4 range...)
        False
        >>> c._contains_int(-1)          # (impossible case, as not in IPv4 range...)
        False

        >>> d = IPv4Container('0.0.0.0', '255.0.0.0/8')
        >>> d._networks                                            # doctest: +NORMALIZE_WHITESPACE
        (IPv4Network('0.0.0.0/32'), IPv4Network('255.0.0.0/8'))
        >>> d._search_sequence
        (0, 1, 4278190080, 4294967296)
        >>> d._contains_int(0)
        True
        >>> d._contains_int(1)
        False
        >>> d._contains_int(2)
        False
        >>> d._contains_int(255)
        False
        >>> d._contains_int(256)
        False
        >>> d._contains_int(4278190079)
        False
        >>> d._contains_int(4278190080)
        True
        >>> d._contains_int(4278190081)
        True
        >>> d._contains_int(4294967294)
        True
        >>> d._contains_int(4294967295)
        True
        >>> d._contains_int(4294967296)  # (impossible case, as not in IPv4 range...)
        False
        >>> d._contains_int(-1)          # (impossible case, as not in IPv4 range...)
        False

        >>> e = IPv4Container('0.0.0.0/24', '0.0.1.0/25', '255.255.255.255')
        >>> e._networks                                            # doctest: +NORMALIZE_WHITESPACE
        (IPv4Network('0.0.0.0/24'), IPv4Network('0.0.1.0/25'),
         IPv4Network('255.255.255.255/32'))
        >>> e._search_sequence
        (0, 384, 4294967295, 4294967296)
        >>> e._contains_int(0)
        True
        >>> e._contains_int(1)
        True
        >>> e._contains_int(2)
        True
        >>> e._contains_int(127)
        True
        >>> e._contains_int(128)
        True
        >>> e._contains_int(129)
        True
        >>> e._contains_int(255)
        True
        >>> e._contains_int(256)
        True
        >>> e._contains_int(257)
        True
        >>> e._contains_int(383)
        True
        >>> e._contains_int(384)
        False
        >>> e._contains_int(385)
        False
        >>> e._contains_int(4278190079)
        False
        >>> e._contains_int(4278190080)
        False
        >>> e._contains_int(4278190081)
        False
        >>> e._contains_int(4294967294)
        False
        >>> e._contains_int(4294967295)
        True
        >>> e._contains_int(4294967296)  # (impossible case, as not in IPv4 range...)
        False
        >>> e._contains_int(-1)          # (impossible case, as not in IPv4 range...)
        False

        >>> f = IPv4Container('0.0.0.4', '0.0.1.0/24', '0.0.0.3',
        ...                   '0.0.0.6', '0.0.0.128/25', '0.0.0.5')
        >>> f._networks                                            # doctest: +NORMALIZE_WHITESPACE
        (IPv4Network('0.0.0.3/32'), IPv4Network('0.0.0.4/31'), IPv4Network('0.0.0.6/32'),
         IPv4Network('0.0.0.128/25'), IPv4Network('0.0.1.0/24'))
        >>> f._search_sequence
        (3, 7, 128, 512)
        >>> f._contains_int(0)
        False
        >>> f._contains_int(1)
        False
        >>> f._contains_int(2)
        False
        >>> f._contains_int(3)
        True
        >>> f._contains_int(4)
        True
        >>> f._contains_int(5)
        True
        >>> f._contains_int(6)
        True
        >>> f._contains_int(7)
        False
        >>> f._contains_int(8)
        False
        >>> f._contains_int(127)
        False
        >>> f._contains_int(128)
        True
        >>> f._contains_int(129)
        True
        >>> f._contains_int(255)
        True
        >>> f._contains_int(256)
        True
        >>> f._contains_int(511)
        True
        >>> f._contains_int(512)
        False
        >>> f._contains_int(513)
        False
        >>> f._contains_int(4294967295)
        False
        >>> f._contains_int(4294967296)  # (impossible case, as not in IPv4 range...)
        False
        >>> f._contains_int(-1)          # (impossible case, as not in IPv4 range...)
        False

        >>> g = IPv4Container(
        ...     # (contains all addresses from the `10.10.10.0/24` network
        ...     # *except* `10.10.10.152`)
        ...     '10.10.10.153/32',
        ...     '10.10.10.160/27',
        ...     '10.10.10.144/29',
        ...     '10.10.10.192/26',
        ...     '10.10.10.128/28',
        ...     '10.10.10.156/30',
        ...     '10.10.10.0/25',
        ...     '10.10.10.154/31',
        ... )
        >>> g._networks                                            # doctest: +NORMALIZE_WHITESPACE
        (IPv4Network('10.10.10.0/25'), IPv4Network('10.10.10.128/28'),
         IPv4Network('10.10.10.144/29'), IPv4Network('10.10.10.153/32'),
         IPv4Network('10.10.10.154/31'), IPv4Network('10.10.10.156/30'),
         IPv4Network('10.10.10.160/27'), IPv4Network('10.10.10.192/26'))
        >>> g._search_sequence == (
        ...     ip_str_to_int('10.10.10.0'),
        ...     ip_str_to_int('10.10.10.152'),
        ...     ip_str_to_int('10.10.10.153'),
        ...     ip_str_to_int('10.10.11.0'),
        ... )
        True
        >>> g._contains_int(ip_str_to_int('10.10.9.255'))
        False
        >>> all(g._contains_int(ip_str_to_int(f'10.10.10.{i}'))
        ...     for i in range(0, 152))
        True
        >>> g._contains_int(ip_str_to_int('10.10.10.152'))
        False
        >>> all(g._contains_int(ip_str_to_int(f'10.10.10.{i}'))
        ...     for i in range(153, 256))
        True
        >>> g._contains_int(ip_str_to_int('10.10.11.0'))
        False

        >>> h = IPv4Container(
        ...     '10.10.10.153/32',
        ...     '10.10.10.160/27',
        ...     '10.10.10.144/29',
        ...     '10.10.10.192/26',
        ...     '10.10.10.0/24',     # <- Note: this one contains all others + '10.10.10.152'
        ...     '10.10.10.128/28',
        ...     '10.10.10.156/30',
        ...     '10.10.10.0/25',
        ...     '10.10.10.154/31',
        ... )
        >>> h._networks
        (IPv4Network('10.10.10.0/24'),)
        >>> h._search_sequence == (
        ...     ip_str_to_int('10.10.10.0'),
        ...     ip_str_to_int('10.10.11.0'),
        ... )
        True
        >>> h._contains_int(ip_str_to_int('10.10.9.255'))
        False
        >>> all(h._contains_int(ip_str_to_int(f'10.10.10.{i}'))
        ...     for i in range(0, 256))
        True
        >>> h._contains_int(ip_str_to_int('10.10.11.0'))
        False

        >>> j = IPv4Container(
        ...     '10.10.10.153/32',
        ...     '10.10.10.160/27',
        ...     '10.10.10.144/29',
        ...     '10.10.10.192/26',
        ...     '10.10.8.0/21',      # <- Note: this one contains all others + much more...
        ...     '10.10.10.128/28',
        ...     '10.10.10.156/30',
        ...     '10.10.10.0/25',
        ...     '10.10.10.154/31',
        ... )
        >>> j._networks
        (IPv4Network('10.10.8.0/21'),)
        >>> j._search_sequence == (
        ...     ip_str_to_int('10.10.8.0'),
        ...     ip_str_to_int('10.10.16.0'),
        ... )
        True
        >>> j._contains_int(ip_str_to_int('10.10.7.255'))
        False
        >>> all(j._contains_int(ip_str_to_int(f'10.10.{a}.{b}'))
        ...     for a in range(8, 16)
        ...         for b in range(0, 256))
        True
        >>> j._contains_int(ip_str_to_int('10.10.16.0'))
        False
        """
        seq = []
        prev_ip_stop = None
        for net in networks:
            ip_start = int(net.network_address)
            ip_stop = int(net.broadcast_address) + 1
            assert ip_start < ip_stop
            assert ip_stop == ip_start + int(f'1{(32 - net.prefixlen) * "0"}', 2)
            if prev_ip_stop == ip_start:
                # Merge the `net`'s IP interval with the previous one.
                assert seq
                seq[-1] = ip_stop
            else:
                assert (
                    prev_ip_stop is None or
                    # This is guaranteed thanks to the invocation of
                    # `collapse_addresses()` in our `__init__()`:
                    prev_ip_stop < ip_start)
                seq.append(ip_start)
                seq.append(ip_stop)
            prev_ip_stop = ip_stop
        assert len(seq) % 2 == 0
        assert seq == sorted(set(seq))
        return tuple(seq)

    def _contains_int(self, ip: int) -> bool:
        """
        Internal helper: the *containment test* implementation based
        on the content of the attribute `_search_sequence` (see the
        internal method `_prepare_search_sequence()`...).

        The computational complexity of the operation is logarithmic, i.e.,
        `O(log n)` (where `n` is `len(_search_sequence)`) -- that's why
        we use it instead of, e.g., a `_networks`-attribute-based linear
        search...
        """
        return bisect.bisect_right(self._search_sequence, ip) % 2 == 1

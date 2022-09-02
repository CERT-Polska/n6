# Copyright (c) 2013-2021 NASK. All rights reserved.

import logging
import socket
from collections.abc import Sequence
from ipaddress import (
    collapse_addresses,
    IPv4Address,
    IPv4Network,
)
from typing import (
    overload,
    Union,
)


LOGGER = logging.getLogger(__name__)


def ip_network_as_tuple(ip_network_str):
    # type: (str) -> tuple[str, int]
    """
    >>> ip_network_as_tuple('10.20.30.40/24')
    ('10.20.30.40', 24)
    """
    ip_str, prefixlen_str = ip_network_str.split("/")
    prefixlen = int(prefixlen_str)
    return ip_str, prefixlen


def ip_network_tuple_to_min_max_ip(ip_network_tuple):
    # type: (tuple[str, int]) -> tuple[int, int]
    """
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 24))
    (169090560, 169090815)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 32))
    (169090601, 169090601)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 0))
    (0, 4294967295)
    """
    ip_str, prefixlen = ip_network_tuple
    ip_int = ip_str_to_int(ip_str)
    min_ip = (((1 << prefixlen) - 1) << (32 - prefixlen)) & ip_int
    max_ip = (((1 << (32 - prefixlen)) - 1)) | ip_int
    return min_ip, max_ip


def ip_str_to_int(ip_str):
    # type: (str) -> int
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
        * membership checking
            - tests if an `IPv4Container` instance contains
            a particular IPv4 address,
        * logical truth test
            - checks if an instance contains any IPv4 address,
            returns False if `IPv4Container` instance does not
            contain any IP, True otherwise.
    This class also provides read-only *networks* property
    containing a sequence of `ipaddress.IPv4Network` instances
    of which `IPv4Container` instance consists.

    Constructor args:
        Each of them should be:
            - an `ipaddress.IPv4Network` instance,
            - an `ipaddress.IPv4Address` instance,
            - an IPv4 address as a `str`, `int` or an integer number
            packed into `bytes` (big-endian), or an IPv4 network as
            a `str` or a two-tuple of an IPv4 address and a netmask
            (i.e., whatever is accepted by the `ipaddress.Ipv4Network`
            constructor).

    Constructor-raised exceptions:
        `ipaddress.IPv4Network` - constructor-related exceptions.
    """

    def __init__(self, *ip_or_network_seq: IPv4AddressOrNetworkDescription) -> None:
        uncollapsed_networks = map(self._convert_to_network, ip_or_network_seq)
        self._networks = tuple(collapse_addresses(uncollapsed_networks))

    @property
    def networks(self) -> Sequence[IPv4Network]:
        """
        Return a sequence of `ipaddress.IPv4Network` objects containing
        only addresses of which the `IPv4Container` instance consists.

        >>> ips = IPv4Container('1.1.1.1')
        >>> list(ips.networks)
        [IPv4Network('1.1.1.1/32')]
        >>> ips2 = IPv4Container('7.7.7.7', '1.1.1.0/24')
        >>> list(ips2.networks)
        [IPv4Network('1.1.1.0/24'), IPv4Network('7.7.7.7/32')]
        >>> ips3 = IPv4Container('2.0.0.0/16', '6.6.0.0/16')
        >>> list(ips3.networks)
        [IPv4Network('2.0.0.0/16'), IPv4Network('6.6.0.0/16')]
        >>> ips4 = IPv4Container('1.1.1.0/24', '1.1.0.0/24')
        >>> list(ips4.networks)
        [IPv4Network('1.1.0.0/23')]
        """
        return self._networks

    @overload
    def __contains__(self, ip: IPv4Address) -> bool:
        ...

    @overload
    def __contains__(self, ip: Union[int, bytes, str]) -> bool:
        ...

    def __contains__(self, ip):
        r"""
        An argument to this method have to be an IPv4 address and
        can be provided as:
            - an `ipaddress.IPv4Address` instance,
            - a `str`,
            - an `int`,
            - an integer number packed into a `bytes` object of length 4,
            with most significant octet first (big-endian).

        >>> ips = IPv4Container('1.1.1.1')
        >>> IPv4Address('1.1.1.1') in ips
        True
        >>> IPv4Address('2.2.2.2') in ips
        False
        >>> '1.1.1.1' in ips
        True
        >>> '2.2.2.2' in ips
        False
        >>> 16843009 in ips
        True
        >>> 2 in ips
        False
        >>> b'\x01\x01\x01\x01' in ips
        True
        >>> b'\x01\x01\x01\x03' in ips
        False
        >>> '1.1.1' in ips
        Traceback (most recent call last):
            ...
        ipaddress.AddressValueError: Expected 4 octets in '1.1.1'
        >>> ips2 = IPv4Container('7.7.7.7', '1.1.1.0/24')
        >>> IPv4Address('1.1.1.2') in ips2
        True
        >>> IPv4Address('8.8.8.8') in ips2
        False
        >>> '7.7.7.7' in ips2
        True
        >>> '8.8.8.8' in ips2
        False
        >>> '1.1.1.6' in ips2
        True
        >>> '1.1.2.2' in ips2
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
        >>> IPv4Address('2.0.1.2') in ips3
        True
        >>> IPv4Address('6.5.4.3') in ips3
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
        """
        if not isinstance(ip, IPv4Address):
            ip = IPv4Address(ip)
        return any(ip in network
                   for network in self._networks)

    def __bool__(self) -> bool:
        """
        Whether this `IPv4Container` contains *at least one address*.

        >>> inst = IPv4Container()
        >>> bool(inst)
        False
        >>> inst2 = IPv4Container('7.7.7.7')
        >>> bool(inst2)
        True
        >>> inst3 = IPv4Container('7.7.7.7', '1.1.1.0/24')
        >>> bool(inst3)
        True
        """
        return True if self._networks else False

    def __repr__(self) -> str:
        """
        >>> IPv4Container('1.1.1.1')
        IPv4Container(IPv4Network('1.1.1.1/32'),)
        >>> IPv4Container('1.1.1.0/24', '1.1.0.0/24')
        IPv4Container(IPv4Network('1.1.0.0/23'),)
        >>> IPv4Container('7.7.7.7', '1.1.1.0/24')
        IPv4Container(IPv4Network('1.1.1.0/24'), IPv4Network('7.7.7.7/32'))
        >>> IPv4Container('2.0.0.0/16', '6.6.0.0/16')
        IPv4Container(IPv4Network('2.0.0.0/16'), IPv4Network('6.6.0.0/16'))
        """
        return f"{type(self).__qualname__}{self._networks}"

    @staticmethod
    def _convert_to_network(ip_or_network: IPv4AddressOrNetworkDescription) -> IPv4Network:
        r"""
        Convert an address or a network into an `ipaddress.IPv4Network` object.

        As an argument, it can take an address or a network in any form
        accepted by the class constructor -- see the description of the constructor.

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

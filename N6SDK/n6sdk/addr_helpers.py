# Copyright (c) 2013-2021 NASK. All rights reserved.

import socket


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

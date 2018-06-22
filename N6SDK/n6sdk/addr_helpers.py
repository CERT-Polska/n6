# -*- coding: utf-8 -*-

# Copyright (c) 2013-2014 NASK. All rights reserved.

import socket


def ip_network_as_tuple(ip_network_str):
    """
    >>> ip_network_as_tuple('10.20.30.40/24')
    ('10.20.30.40', 24)
    """
    ip_str, net_str = ip_network_str.split("/")
    net_int = int(net_str)
    return ip_str, net_int  # note: ip is a string, net is a number


def ip_network_tuple_to_min_max_ip(ip_network_tuple):
    """
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 24))
    (169090560, 169090815)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 32))
    (169090601, 169090601)
    >>> ip_network_tuple_to_min_max_ip(('10.20.30.41', 0))
    (0, 4294967295)
    """
    ip_str, net_int = ip_network_tuple
    ip_int = ip_str_to_int(ip_str)
    min_ip = (((1 << net_int) - 1) << (32 - net_int)) & ip_int
    max_ip = (((1 << (32 - net_int)) - 1)) | ip_int
    return min_ip, max_ip


def ip_str_to_int(ip_str):
    """
    >>> ip_str_to_int('10.20.30.41')
    169090601
    """
    return int(socket.inet_aton(ip_str).encode('hex'), 16)

# -*- coding: utf-8 -*-

import unittest

from unittest_expander import expand, foreach, param

from n6.collectors.badips import BadipsServerExploitCollector


@expand
class TestBadIpsCollector(unittest.TestCase):

    @foreach([
        param(
            ips_string='12.12.12.12\n',
            category_root='sql',
            category_leaf='sql-injection',
            result='12.12.12.12;sql-injection sql attack'
        ),
        param(
            ips_string='123.123.123.123\n321.321.321.321\n99.88.77.66\n',
            category_root='ssh',
            category_leaf='test',
            result='123.123.123.123;test ssh attack\n321.321.321.321;test ssh attack\n' +
                   '99.88.77.66;test ssh attack'
        ),
    ])
    def test_badips_collector_ip_list_formatting(self, ips_string, category_root, category_leaf,
                                                 result):
        self.assertEqual(result,
                         BadipsServerExploitCollector._add_fields_name(ips=ips_string,
                                                                       category_root=category_root,
                                                                       category_leaf=category_leaf))

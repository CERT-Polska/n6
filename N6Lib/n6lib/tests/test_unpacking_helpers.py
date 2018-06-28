# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

import unittest

from n6lib.unpacking_helpers import gunzip_from_string, iter_unzip_from_string


class Test__gunzip_from_string(unittest.TestCase):

    def test(self):
        compressed = (
            '\x1f\x8b\x08\x08u\xa7\x94Q\x00\x03TEST\x00+\xae\xcc+I\xac\xb0RH'
            '\xcf\xc9O\xe2\xe2\xd2\xd2+\xa8L\xe6\xd2+(\xca\xcfJM.\x012*SR'
            '\xcb\xe0\xbc\xe2\xd4\x92\x92\xcc\xbc\xf4b..\x00\x98^\xaaF6\x00'
            '\x00\x00')
        decompressed = (
            'syntax: glob\n\n*.pyc\n.project\n.pydevproject\n.settings\n\n')
        self.assertEqual(gunzip_from_string(compressed), decompressed)


class Test__iter_unzip_from_string(unittest.TestCase):

    def setUp(self):
        self.zipped = (
            'PK\x03\x04\x14\x00\x00\x00\x08\x00\xf1[\xb0B\x98^\xaaF/\x00\x00'
            '\x006\x00\x00\x00\x0c\x00\x1c\x00n6/.hgignoreUT\t\x00\x03u\xa7'
            '\x94Qy\xa7\x94Qux\x0b\x00\x01\x04\xe8\x03\x00\x00\x04\xe8\x03'
            '\x00\x00+\xae\xcc+I\xac\xb0RH\xcf\xc9O\xe2\xe2\xd2\xd2+\xa8L'
            '\xe6\xd2+(\xca\xcfJM.\x012*SR\xcb\xe0\xbc\xe2\xd4\x92\x92\xcc'
            '\xbc\xf4b..\x00PK\x03\x04\n\x00\x00\x00\x00\x00\xdd|\xafB<&'
            '\x891\x04\x00\x00\x00\x04\x00\x00\x00\t\x00\x1c\x00n6/READMEUT'
            '\t\x00\x03\xf1\x8f\x93Q*\x9f\x93Qux\x0b\x00\x01\x04\xe8\x03\x00'
            '\x00\x04\xe8\x03\x00\x00n6.\nPK\x01\x02\x1e\x03\x14\x00\x00\x00'
            '\x08\x00\xf1[\xb0B\x98^\xaaF/\x00\x00\x006\x00\x00\x00\x0c\x00'
            '\x18\x00\x00\x00\x00\x00\x01\x00\x00\x00\xa4\x81\x00\x00\x00'
            '\x00n6/.hgignoreUT\x05\x00\x03u\xa7\x94Qux\x0b\x00\x01\x04\xe8'
            '\x03\x00\x00\x04\xe8\x03\x00\x00PK\x01\x02\x1e\x03\n\x00\x00'
            '\x00\x00\x00\xdd|\xafB<&\x891\x04\x00\x00\x00\x04\x00\x00\x00'
            '\t\x00\x18\x00\x00\x00\x00\x00\x01\x00\x00\x00\xa4\x81u\x00\x00'
            '\x00n6/READMEUT\x05\x00\x03\xf1\x8f\x93Qux\x0b\x00\x01\x04\xe8'
            '\x03\x00\x00\x04\xe8\x03\x00\x00PK\x05\x06\x00\x00\x00\x00\x02'
            '\x00\x02\x00\xa1\x00\x00\x00\xbc\x00\x00\x00\x00\x00')
        self.dir = 'n6/'
        self.file_names_and_contents = [
            ('README',
             'n6.\n'),
            ('.hgignore',
             'syntax: glob\n\n*.pyc\n.project\n.pydevproject\n.settings\n\n')]

    def test_all_filenames(self):
        expected = self.file_names_and_contents
        real = list(iter_unzip_from_string(self.zipped))
        self.assertItemsEqual(expected, real)

    #def test_with_password(self):
    #    TODO

    def test_specified_filenames(self):
        name, content = self.file_names_and_contents[1]  # .hgignore
        expected = [(name, content)]
        real = list(iter_unzip_from_string(
            self.zipped,
            filenames=['IGNORED-NON-EXISTENT', name, 'another ignored...']))
        self.assertItemsEqual(expected, real)

    def test_specified_filenames_yielding_with_dirs(self):
        name, content = self.file_names_and_contents[1]  # .hgignore
        expected = [(self.dir + name, content)]
        real = list(iter_unzip_from_string(
            self.zipped,
            filenames=['IGNORED-NON-EXISTENT', name, 'another ignored...'],
            yielding_with_dirs=True))
        self.assertItemsEqual(expected, real)

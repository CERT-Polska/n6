# Copyright (c) 2022-2023 NASK. All rights reserved.

import unittest

from unittest_expander import (
    expand,
    foreach,
)

from n6adminpanel.app import AdminPanel


@expand
class TestAdminPanel_config_filename_regex(unittest.TestCase):                             # noqa

    @foreach(
        'admin_panel.conf',
        'admin_panel_and_scripts.conf',
        'scripts_and_admin_panel.conf',
        'n6adminpanel.conf',
        'admin_panel2.conf',
        '!@#$%^&*()AdminPanel.Tra-la-la-la-la.conf',
        'adMin---paNel.conf',
        '_admin_panel.conf',
        '_admin_panel_.conf',
        'adminpanel_.conf',
        '1Admin2paneL3.conf',
    )
    def test_config_filename_regex_matches(self, filename):
        assert AdminPanel._admin_panel_specific_config_filename_regex.search(filename)

    @foreach(
        'panel_admin.conf',
        'admin.conf',
        'panel.conf',
        'admin_and_scripts.conf',
        'scripts_and_admin.conf',
        'panel_and_scripts.conf',
        'scripts_and_panel.conf',
        'aadmin_panel.conf',
        'adminnpanel.conf',
        'admin_panell.conf',
        '!@#$%^&*()aAdminPanel:Tra-la-la-la-la.conf',
        'admin_panel.Conf',
        'admin_panel.conF',
        'admin_panel_conf',
        'admin_panel5conf',
        'admin_panel.spam',
    )
    def test_config_filename_regex_does_not_match(self, filename):
        assert not AdminPanel._admin_panel_specific_config_filename_regex.search(filename)

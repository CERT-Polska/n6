#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013-2018 NASK. All rights reserved.

# NOTE: more of the config-related stuff is in n6lib.config

import os
import os.path
import shutil
import sys

from n6lib.const import USER_DIR, ETC_DIR


def install_default_config():
    """
    Copy default N6Core conf files to '/etc/n6' or '~/.n6'.
    """

    def confirm_yes_no(msg, default=True):
        print "%s [%s]" % (msg, "Y/n" if default else "y/N")
        # raw_input returns the empty string for "enter"
        yes = set(['yes', 'y', 'ye'])
        no = set(['no', 'n'])
        if default:
            yes.add("")
        else:
            no.add("")
        while True:
            choice = raw_input().lower()
            if choice in yes:
                return True
            elif choice in no:
                return False
            else:
                sys.stdout.write("Please respond with 'yes' or 'no': ")

    def check_existing_dir_content(install_to, alternative_to):
        if os.path.isdir(install_to) and os.listdir(install_to):
            if confirm_yes_no(
                    "Directory '%s' is not empty. Remove existing files?" % install_to,
                    default=False):
                shutil.rmtree(install_to)
                os.mkdir(install_to)
            elif alternative_to is not None and confirm_yes_no(
                    "Install in '%s' instead?" % alternative_to):
                install_to = alternative_to
                alternative_to = None
                if os.path.isdir(install_to) and os.listdir(install_to):
                    if confirm_yes_no(
                            "Directory '%s' is not empty. Remove existing files?" % install_to,
                            default=False):
                        shutil.rmtree(install_to)
                        os.mkdir(install_to)
                    else:
                        print "Ok. Exiting"
                        sys.exit(0)
            else:
                print "Ok. Exiting"
                sys.exit(0)
        return install_to, alternative_to

    if not confirm_yes_no("Copy sample configuration files to the system?"):
        print "Ok. Exiting"
        sys.exit(0)

    etcdir = ETC_DIR
    userdir = USER_DIR

    if not os.path.isdir(etcdir):
        try:
            os.makedirs(etcdir)
        except (OSError, IOError):
            pass

    if os.access(etcdir, os.W_OK):
        install_to = etcdir
        alternative_to = userdir
    elif confirm_yes_no("No write access to '%s'. Write to '%s' instead?" % (etcdir, userdir)):
        install_to = userdir
        alternative_to = None
    else:
        print "Ok. Exiting"
        sys.exit(0)

    install_to, alternative_to = check_existing_dir_content(install_to, alternative_to)


    from pkg_resources import (
        Requirement,
        resource_filename,
        resource_listdir,
        cleanup_resources)  #@UnresolvedImport

    try:
        config_template_dir = 'n6/data/conf/'
        files = resource_listdir(Requirement.parse("n6"), config_template_dir)
        for f in files:
            filename = resource_filename(Requirement.parse("n6"), os.path.join(config_template_dir, f))
            try:
                if not os.path.isdir(install_to):
                    os.makedirs(install_to)
                shutil.copy(filename, os.path.join(install_to, f))
            except (IOError, OSError):
                if alternative_to is not None and confirm_yes_no(
                        "Cannot create config files in '%s'. "
                        "Create in '%s' instead?" % (install_to, alternative_to)):
                    install_to, _ = check_existing_dir_content(alternative_to, None)
                    try:
                        if not os.path.isdir(install_to):
                            os.makedirs(install_to)
                        shutil.copy(filename, os.path.join(install_to, f))
                    except (IOError, OSError):
                        print "Error while copying sample conf files to '%s'. Exiting." % install_to
                        sys.exit(1)
                else:
                    print "Ok. Exiting"
                    sys.exit(0)
    finally:
        cleanup_resources()
    print "Success."

# Copyright (c) 2015-2021 NASK. All rights reserved.

import os.path as osp
import pkgutil
import sys

from n6lib.class_helpers import all_subclasses
from n6lib.common_helpers import open_file

CONF_TEMPLATE = None


def find_parsers():
    import n6datasources
    from n6datasources.parsers.base import BaseParser
    console_scripts_list = []
    dirname = osp.dirname(osp.abspath(n6datasources.parsers.__file__))
    for importer, package_name, _ in pkgutil.iter_modules([dirname]):
        full_package_name = 'n6datasources.parsers.%s' % package_name
        if full_package_name not in sys.modules and package_name != "base":
            module = importer.find_module(package_name).load_module()
    for pclass in all_subclasses(BaseParser): # @UndefinedVariable
        if pclass.__module__ == "n6datasources.parsers.base":
            continue
        if pclass.__qualname__.startswith('_'):
            continue
        script_name = pclass.__qualname__.split(".")[-1].lower().replace("parser", "")
        console_line = "n6parser_%s" % (script_name)
        console_scripts_list.append(console_line)
    return console_scripts_list


def create_supervisord_conf(program_name):
    with open_file('programs/%s.conf' % program_name, "w") as f:
        f.write(CONF_TEMPLATE.format(program_name=program_name, program_command=program_name))


def load_template():
    global CONF_TEMPLATE
    with open_file('program_template.tmpl', 'r') as f:
        CONF_TEMPLATE = f.read()


def main():
    load_template()
    for parser in find_parsers():
        create_supervisord_conf(parser)


if __name__ == '__main__':
    main()

# Copyright (c) 2015-2025 NASK. All rights reserved.

import importlib
import pathlib
import pkgutil
import sys

from n6lib.class_helpers import all_subclasses
from n6lib.common_helpers import (
    open_file,
    read_file,
)


_DIR = pathlib.Path(__file__).resolve(strict=True).parent


def main():
    template = read_file(_DIR / 'program_template.tmpl')
    for program_name in generate_parser_program_names():
        create_supervisord_conf(template, program_name)


def generate_parser_program_names():
    _import_parser_modules()
    for cls in _get_parser_classes():
        distinct_part = cls.__name__.lower().removesuffix('parser')
        yield f'n6parser_{distinct_part}'

def _get_parser_classes():
    from n6datasources.parsers.base import BaseParser
    return [cls for cls in all_subclasses(BaseParser)
            if (cls.__module__ != 'n6datasources.parsers.base'
                and cls.__module__.split('.')[1:2] != ['tests']
                and not cls.__name__.startswith('_'))]

def _import_parser_modules():
    pkg_path_list = [p for p in sys.path if 'n6datasources' in p.lower()]
    for _, modname, _ in pkgutil.walk_packages(pkg_path_list):
        if (modname.count('.') >= 2
              and modname.split('.')[0].startswith('n6datasources')
              and modname.split('.')[1] == 'parsers'):
            importlib.import_module(modname)


def create_supervisord_conf(template, program_name):
    with open_file(_DIR / f'programs/{program_name}.conf', 'w') as f:
        f.write(template.format(program_name=program_name, program_command=program_name))


if __name__ == '__main__':
    main()

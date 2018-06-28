# Copyright (c) 2013-2018 NASK. All rights reserved.

import glob
import os.path as osp
import sys

from setuptools import setup, find_packages
import pkgutil


setup_dir = osp.dirname(osp.abspath(__file__))

with open(osp.join(setup_dir, '.n6-version')) as f:
    n6_version = f.read().strip()


if "--collectors-only" in sys.argv:
    collectors_only = True
    sys.argv.remove("--collectors-only")
else:
    collectors_only = False


def setup_data_line_generator(filename_base):
    path_base = osp.join(setup_dir, filename_base)
    path_glob = path_base + '*'
    for path in glob.glob(path_glob):
        with open(path) as f:
            for raw_line in f:
                yield raw_line.strip()

def find_scripts():
    console_scripts_list.extend(setup_data_line_generator('console_scripts'))

def all_subclasses(cls):
    """
    Return a set of all direct and indirect subclasses of the given class.
    """
    ### IMPORTANT: this is a copy of n6lib.class_helpers.all_subclasses()
    #   (copied because it cannot be imported here).
    #   Please do not modify this function's code without
    #   modifying n6lib.class_helpers.all_subclasses() first!
    #   (i.e., they should be kept in sync)
    direct_subclasses = cls.__subclasses__()
    return set(direct_subclasses).union(
            indirect
            for direct in direct_subclasses
                for indirect in all_subclasses(direct))

def find_parsers():
    global console_scripts_list
    from n6.parsers.generic import BaseParser
    dirname = "n6/parsers"
    for importer, package_name, _ in pkgutil.iter_modules([dirname]):
        full_package_name = 'n6.parsers.%s' % package_name
        if full_package_name not in sys.modules and package_name != "generic":
            module = importer.find_module(package_name
                        ).load_module(full_package_name)
    for pclass in all_subclasses(BaseParser): # @UndefinedVariable
        if pclass.__module__ == "n6.parsers.generic":
            continue
        if pclass.__name__.startswith('_'):
            continue
        script_name = pclass.__name__.split(".")[-1].lower().replace("parser", "")
        entry_name = "%s:%s_main" % (pclass.__module__, pclass.__name__.split(".")[-1])
        console_line = "n6parser_%s = %s" % (script_name, entry_name)
        console_scripts_list.append(console_line)

def find_collectors():
    global console_scripts_list
    from n6.collectors.generic import AbstractBaseCollector
    dirname = "n6/collectors"
    for importer, package_name, _ in pkgutil.iter_modules([dirname]):
        full_package_name = 'n6.collectors.%s' % package_name
        if full_package_name not in sys.modules and package_name != "generic":
            module = importer.find_module(package_name
                        ).load_module(full_package_name)
    for pclass in all_subclasses(AbstractBaseCollector): # @UndefinedVariable
        if pclass.__module__ == "n6.collectors.generic":
            continue
        if pclass.__name__.startswith('_'):
            continue
        script_name = pclass.__name__.split(".")[-1].lower().replace("collector", "")
        entry_name = "%s:%s_main" % (pclass.__module__, pclass.__name__.split(".")[-1])
        console_line = "n6collector_%s = %s" % (script_name, entry_name)
        console_scripts_list.append(console_line)


requirements = ['n6lib==' + n6_version]
console_scripts_list = ['n6config = n6.base.config:install_default_config']

if not collectors_only:
    find_scripts()
    find_parsers()
find_collectors()


setup(
    name="n6",
    version=n6_version,

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    tests_require=['mock==1.0.1', 'unittest_expander'],
    test_suite='n6.tests',
    install_requires=requirements,
    entry_points={
        'console_scripts': console_scripts_list,
    },

    description='The core components of *n6*',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Security',
    ],
    keywords='n6 network incident exchange',
)

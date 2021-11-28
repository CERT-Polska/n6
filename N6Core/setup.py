# Copyright (c) 2013-2021 NASK. All rights reserved.

import glob
import os.path as osp
import sys

from setuptools import setup, find_packages
import pkgutil


if "--collectors-only" in sys.argv:
    collectors_only = True
    sys.argv.remove("--collectors-only")
else:
    collectors_only = False

setup_dir, setup_filename = osp.split(osp.abspath(__file__))
setup_human_readable_ref = osp.join(osp.basename(setup_dir), setup_filename)

def get_n6_version(filename_base):
    path_base = osp.join(setup_dir, filename_base)
    path_glob_pattern = path_base + '*'
    # The non-suffixed path variant should be
    # tried only if another one does not exist.
    matching_paths = sorted(glob.iglob(path_glob_pattern),
                            reverse=True)
    try:
        path = matching_paths[0]
    except IndexError:
        sys.exit('[{}] Cannot determine the n6 version '
                 '(no files match the pattern {!r}).'
                 .format(setup_human_readable_ref,
                         path_glob_pattern))
    try:
        with open(path) as f:                                             #3: add: `, encoding='ascii'`
            return f.read().strip()
    except (OSError, UnicodeError) as exc:
        sys.exit('[{}] Cannot determine the n6 version '
                 '(an error occurred when trying to '
                 'read it from the file {!r} - {}).'
                 .format(setup_human_readable_ref,
                         path,
                         exc))

def setup_data_line_generator(filename_base):
    path_base = osp.join(setup_dir, filename_base)
    path_glob_pattern = path_base + '*'
    # Here we sort the paths just to make the order of operations deterministic.
    matching_paths = sorted(glob.iglob(path_glob_pattern))
    for path in matching_paths:
        try:
            with open(path) as f:                                         #3: add: `, encoding='ascii'`
                for raw_line in f:
                    yield raw_line.strip()
        except (OSError, UnicodeError) as exc:
            sys.exit('[{}] Could not read from the file {!r} ({})'
                     .format(setup_human_readable_ref, path, exc))

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


n6_version = get_n6_version('.n6-version')

requirements = [
    'n6sdk-py2==' + n6_version,
    'n6lib-py2==' + n6_version,
    'n6corelib-py2==' + n6_version,
]
console_scripts_list = ['n6config = n6.base.config:install_default_config']

if not collectors_only:
    find_scripts()
    find_parsers()
find_collectors()


setup(
    name="n6core-py2",
    version=n6_version,

    packages=find_packages(),
    include_package_data=True,
    python_requires='==2.7.*',
    zip_safe=False,
    tests_require=['mock==3.0.5', 'unittest_expander==0.3.1'],
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

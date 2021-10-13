# Copyright (c) 2013-2021 NASK. All rights reserved.

import glob
import os.path as osp
import sys

from setuptools import setup, find_packages


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
                 '(no files match the pattern {!a}).'
                 .format(setup_human_readable_ref,
                         path_glob_pattern))
    try:
        with open(path, encoding='ascii') as f:
            return f.read().strip()
    except (OSError, UnicodeError) as exc:
        sys.exit('[{}] Cannot determine the n6 version '
                 '(an error occurred when trying to '
                 'read it from the file {!a} - {}).'
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
            with open(path, encoding='ascii') as f:
                for raw_line in f:
                    yield raw_line.strip()
        except (OSError, UnicodeError) as exc:
            sys.exit('[{}] Could not read from the file {!a} ({})'
                     .format(setup_human_readable_ref, path, exc))

def list_console_scripts():
    return [line
            for line in setup_data_line_generator('console_scripts')
            if line and not line.startswith('#')]


n6_version = get_n6_version('.n6-version')
requirements = ['n6sdk==' + n6_version, 'n6lib==' + n6_version, 'n6datapipeline==' + n6_version]
console_scripts = list_console_scripts()

setup(
    name='n6datasources',
    version=n6_version,

    packages=find_packages(),
    include_package_data=True,
    python_requires='==3.9.*',
    zip_safe=False,
    tests_require=['unittest_expander==0.3.1'],
    test_suite='n6datasources.tests',
    install_requires=requirements,
    entry_points={
        'console_scripts': console_scripts,
    },

    description='The data collector components and parser components of *n6*',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.9',
        'Topic :: Security',
    ],
    keywords='n6 network incident exchange data sources',
)

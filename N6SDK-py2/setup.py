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


n6_version = get_n6_version('.n6-version')

requirements = []
dep_links = []
with open(osp.join(setup_dir, 'requirements')) as f:                      #3: add: `, encoding='ascii'`
    for raw_line in f:
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        req = line.split('\t')
        requirements.append(req[0])
        try:
            dep_links.append(req[1])
        except IndexError:
            pass


setup(
    name="n6sdk",
    version=n6_version,

    packages=find_packages(),
    dependency_links=dep_links,
    install_requires=requirements,
    include_package_data=True,
    python_requires='==2.7.*',
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'n6sdk_api_test = n6sdk._api_test_tool.api_test_tool:main',
        ],
    },

    description='An *n6*-like REST API server framework.',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'Framework :: Pyramid',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',  #3
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    keywords='n6 network incident exchange rest api library framework',
)

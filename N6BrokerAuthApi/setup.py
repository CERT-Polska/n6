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


n6_version = get_n6_version('.n6-version')

requires = [
    'n6lib==' + n6_version,
    'pyramid==1.10.8',
]

setup(
    name='n6brokerauthapi',
    version=n6_version,

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    python_requires='==3.9.*',
    install_requires=requires,
    entry_points="""\
        [paste.app_factory]
        main = n6brokerauthapi:main
    """,
    tests_require=['unittest_expander==0.4.4'],
    test_suite='n6brokerauthapi.tests',
    description='Authentication and authorization API for RabbitMQ',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.9',
        "Framework :: Pyramid",
        'Topic :: Security',
    ],
    keywords='n6 network incident exchange stomp stream api rabbitmq auth backend '
             'authorization authentication',
)

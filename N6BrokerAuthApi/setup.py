# Copyright (c) 2013-2019 NASK. All rights reserved.

import os.path as osp

from setuptools import setup, find_packages


setup_dir = osp.dirname(osp.abspath(__file__))

with open(osp.join(setup_dir, '.n6-version')) as f:
    n6_version = f.read().strip()


requires = [
    'n6lib==' + n6_version,
    'pyramid',
    'paste',
    'typing',
]

setup(
    name='n6brokerauthapi',
    version=n6_version,

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    entry_points="""\
        [paste.app_factory]
        main = n6brokerauthapi:main
    """,
    tests_require=['mock==1.0.1', 'pytest', 'unittest_expander'],
    test_suite='n6brokerauthapi.tests',
    description='Authentication and authorization API for RabbitMQ',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        "Framework :: Pyramid",
        'Topic :: Security',
    ],
    keywords='n6 network incident exchange stomp stream api rabbitmq auth backend '
             'authorization authentication',
)

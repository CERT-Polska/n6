# Copyright (c) 2013-2018 NASK. All rights reserved.

import os.path as osp

from setuptools import setup, find_packages


setup_dir = osp.dirname(osp.abspath(__file__))

with open(osp.join(setup_dir, '.n6-version')) as f:
    n6_version = f.read().strip()


requires = [
    'n6lib==' + n6_version,

    'pyramid',
    'SQLAlchemy==0.9.10',
    'transaction',
    'pyramid_debugtoolbar',
    'zope.sqlalchemy',
    'waitress',
    'mysql-python',
    'paste',
]

setup(
    name='n6web',
    version=n6_version,

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    tests_require=["mock==1.0.1", "unittest_expander"],
    test_suite='n6web.tests',
    install_requires=requires,
    entry_points="""\
        [paste.app_factory]
        main = n6web:main
        main_test_api = n6web:main_test_api
    """,

    description='The *n6* REST API',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Framework :: Pyramid',
        'Topic :: Security',
    ],
    keywords='n6 network incident exchange rest api',
)

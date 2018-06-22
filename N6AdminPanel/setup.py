from setuptools import setup, find_packages

requires = [
    'n6lib',

    'Flask==1.0.2',
    'Flask-Admin==1.5.1',
    'SQLAlchemy==0.9.10',
    'WTForms==2.1',
]

setup(
    name='n6adminpanel',
    version='2.0.0',

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,

    description='The *n6* admin panel web application',
    url='https://github.com/CERT-Polska/n6',
    maintainer='CERT Polska',
    maintainer_email='n6@cert.pl',
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        "Framework :: Flask",
        'Topic :: Security',
    ],
    keywords='n6 network incident exchange admin panel',
)

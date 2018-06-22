.. _n6sdk_api_test_tool:

``n6sdk_api_test``: API testing tool
====================================

Overview
--------

The ``n6sdk_api_test`` script is a simple tool to perform basic
validation of your *n6sdk*-based REST API.

In the current version of the tool, *validation* consist of the
following steps:

1. inferring basic information about the tested API + testing
   essential compliance with the general *n6* specification;
2. testing a query containing two (randomly selected) *legal*
   parameters;
3. testing queries containing some *illegal* parameters;
4. testing queries containing (single) *legal* parameters;
5. testing queries containing one parameter, using various
   values of it.

API testing tool provides feedback printed in a plain text format.
The report is structured in sections for every test case category.
The output is more informative when the ``--verbose`` option is used.

The test data set is prepared automatically; how is it done depends on
the query parameters placed in the tool's config file.  Hence, it is
the user's responsibility to select the base URL containing such query
parameters that the response will reflect the internal structure of
data records from the database as well as possible.  In other words,
the user is responsible for selecting a query that allows to pick out
the most diverse data sample.

Because of simplicity of the ``n6sdk_api_test`` tool -- and
considering that the script employs a lot of randomization -- it may
be worth running the tool more than once.  Experimenting with
different settings in the ``[constant_params]`` section of the tool's
config can also be a good idea.


Installation
------------

The script is automatically installed in the appropriate place when
you install *n6sdk* by running ``python setup.py install`` (see:
:ref:`dev_install` or :ref:`prod_install`).


Configuration and usage
-----------------------

To use ``n6sdk_api_test`` follow these steps:

1. Generate the config file base:

.. code-block:: bash

    $ n6sdk_api_test --generate-config > config.ini

2. Adjust the generated ``config.ini`` file:

   * provide the base URL of the tested API resource;

   * specify mandatory query parameters (``time.min`` etc.; see the
     comment in the generated config file);

   * specify SSL certificate/key paths in case of SSL-based method
     of authentication, or username/password in case of basic HTTP
     authentication (if required by the tested API).

3. Run the script, e.g.:

.. code-block:: bash

    $ n6sdk_api_test -c config.ini

Note that the resultant report is printed to the standard output so
one can easily write it to a file:

.. code-block:: bash

    $ n6sdk_api_test -c config.ini > report.txt

To see the available options:

.. code-block:: bash

    $ n6sdk_api_test -h

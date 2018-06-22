.. _tutorial:

********
Tutorial
********

This tutorial describes how to use the *n6sdk* library to implement an
*n6*-like REST API that provides access to your own network incident
data source.


.. _setting_up_working_env:

Setting up the development environment
======================================

.. _working_env_prerequisites:

Prerequisites
-------------

You need to have:

* A Linux system + the *bash* shell used to interact with it + basic
  Unix-like OS tools such as *mkdir*, *cat* etc. (other platforms and
  tools could also be used -- but this tutorial assumes using the
  aforementioned ones) + your favorite text editor installed;
* the *Python 2.7* language interpreter installed (on Debian GNU/Linux
  it can be installed with the command: ``sudo apt-get install
  python2.7``);
* The *git* version control system installed (on Debian GNU/Linux it
  can be installed with the command: ``sudo apt-get install git``);
* the *virtualenv* tool installed (see:
  http://virtualenv.readthedocs.org/en/latest/installation.html; on
  Debian GNU/Linux it can be installed with the command: ``sudo apt-get
  install python-virtualenv``);
* Internet access.


.. _obtaining_source_code:

Obtaining the *n6sdk* source code
---------------------------------

We will start with creating the "workbench" directory for all our
activities:

.. code-block:: bash

   $ mkdir <the workbench directory>

(Of course, ``<the workbench directory>`` needs to be replaced with
the actual name (absolute path) of the directory you want to create.)

Then, we need to clone the *n6sdk* source code repository:

.. code-block:: bash

   $ cd <the workbench directory>
   $ git clone https://github.com/CERT-Polska/n6sdk.git

Now, in the ``<the workbench directory>/n6sdk/`` subdirectory we have
the source code of the *n6sdk* library.


.. _dev_install:

Installing and setting up the necessary stuff
---------------------------------------------

Next, we will create and activate our Python *virtual environment*:

.. code-block:: bash

   $ virtualenv dev-venv
   $ source dev-venv/bin/activate

Then, we can install the *n6sdk* library:

.. code-block:: bash

   $ cd n6sdk
   $ python setup.py install

Then, we need to create our project:

.. code-block:: bash

   $ cd ..
   $ pcreate -s n6sdk Using_N6SDK

-- where ``Using_N6SDK`` is the name of our new *n6sdk*-based project.
Obviously, when creating your real project you will want to pick
another name.  Anyway, for the rest of this tutorial we will use
``Using_N6SDK`` as the project name (and, consequently,
``using_n6sdk`` as the "technical" package name, automatically
derived from the given project name).

Now, we have the skeleton of our new project.  You may want to
customize some details in the newly created files, especially the
*version* and *description* fields in ``Using_N6SDK/setup.py``.

Then, we need to install our new project *for development*:

.. code-block:: bash

   $ cd Using_N6SDK
   $ python setup.py develop

We can check whether everything up to now went well by running the
Python interpreter...

.. code-block:: bash

   $ cd ..
   $ python

...and trying to import some of the installed components:

   >>> import n6sdk
   >>> import n6sdk.data_spec.fields
   >>> n6sdk.data_spec.fields.Field
   <class 'n6sdk.data_spec.fields.Field'>
   >>> import using_n6sdk
   >>> exit()


.. _data_processing_and_arch:

Overview of data processing and architecture
============================================

When a client sends a **HTTP request** to an *n6sdk*-based REST API,
the following data processing is performed on the server side:

1. **Receiving the HTTP request**

   *n6sdk* uses the *Pyramid* library (see:
   http://docs.pylonsproject.org/projects/pyramid/en/1.5-branch/) to
   perform processing related to HTTP communication, request data (for
   example, extracting query parameters from the URL's query string)
   and routing (deciding what function shall be invoked with what
   arguments depending on the given URL) -- however there are some
   *n6sdk*-specific wrappers and helpers (used to adjust various
   important factors):
   :class:`n6sdk.pyramid_commons.DefaultStreamViewBase`,
   :class:`n6sdk.pyramid_commons.HttpResource` and
   :class:`n6sdk.pyramid_commons.ConfigHelper` (see below:
   :ref:`gluing_it_together`).  These three classes can be customized
   by subclassing them and extending appropriate methods, however it is
   beyond the scope of this tutorial.

2. **Authentication**

   Authentication is performed using a mechanism provided by the
   *Pyramid* library: *authentication policies*. The simplest policy
   is implemented as the
   :class:`n6sdk.pyramid_commons.AnonymousAuthenticationPolicy` class
   (it is a dummy policy: all clients are identified as
   ``"anonymous"``); it can be replaced with a custom one (see below:
   :ref:`custom_authn_policy`).

   The result is an object containing some authentication data.

3. **Cleaning the query parameters provided by the client**

   Here "cleaning" means: validation and adjustment (normalization) of
   the parameters (already extracted from the request's URL).

   An instance of a *data specification class* (see below:
   :ref:`data_spec_class`) is responsible for doing that.

   The result is a dictionary containing the cleaned query parameters.

4. **Retrieving the result data from the data backend API**

   The *data backend API*, responsible for interacting with the actual
   data storage, needs to be implemented as a class (see below:
   :ref:`data_backend_api`).

   For a client request (see above: *1. Receiving the HTTP request*),
   an appropriate method of the sole instance of this class is called
   with the authentication data (see above: *2. Authentication*) and
   the cleaned client query parameters dictionary (see above:
   *3. Cleaning query parameters...*) as call arguments.

   The result of the call is an iterator which yields dictionaries,
   each containing the data of one network incident.

5. **Cleaning the result data**

   Each of the yielded dictionaries is cleaned.  Here "cleaning"
   means: validation and adjustment (normalization) of the result
   data.

   An instance of a *data specification class* (see below:
   :ref:`data_spec_class`) is responsible for doing that.

   The result is another iterator (which yields dictionaries,
   each containing cleaned data of one network incident).

6. **Rendering the HTTP response**

   The yielded cleaned dictionaries are processed to produce
   consecutive fragments of the HTTP response which are successively
   sent to the client.  The key component responsible for transforming
   the dictionaries into the response body is a *renderer*.  Note that
   *n6sdk* renderers (being a custom *n6sdk* concept, distinct from
   *Pyramid* renderers) are able to process data in an iterator
   ("stream-like") manner, so even if the resultant response body is
   huge it does not have to fit as a whole in the server's memory.

   The *n6sdk* library provides two standard renderers: ``json`` (to
   render JSON-formatted responses) and ``sjson`` (to render responses
   in a format similar to JSON but more convenient for "stream-like"
   or "pipeline" data processing: each line is a separate JSON
   document, containing the data of one network incident).

   Implementing and registering custom renderers is possible, however
   it is beyond the scope of this tutorial.


.. _data_spec_class:

Data specification class
========================

Basics
------

A *data specification* determines:

* how query parameters (already extracted from the query string part
  of the URL of a client HTTP request) are cleaned (before being
  passed in to the data backend API) -- that is:

  * what are the legal parameter names;
  * whether particular parameters are required or optional;
  * what are valid values of particular parameters (e.g.: a
    ``time.min`` value must be a valid *ISO-8601*-formatted date and
    time);
  * whether, for a particular parameter, there can be many alternative
    values or only one value (e.g.: ``time.min`` can have only one
    value, and ``ip`` can have multiple values);
  * how values of a particular parameter are normalized (e.g.: a
    ``time.min`` value is always transformed to a Python
    :class:`datetime.datetime` object, converting any time zone
    information to UTC);

* how result dictionaries (each containing the data of one incident)
  yielded by the data backend API are cleaned (before being passed in
  to a response renderer) -- that is:

  * what are the legal result keys;
  * whether particular items are required or optional;
  * what are valid types and values of particular items (e.g.: a
    ``time`` value must be either a :class:`datetime.datetime` object
    or a string being a valid *ISO-8601*-formatted date and time);
  * how particular items are normalized (e.g.: a ``time`` value is
    always transformed to a Python :class:`datetime.datetime` object,
    converting any time zone information to UTC).

The declarative way of defining a *data specification* is somewhat
similar to domain-specific languages known from ORMs (such as the
*SQLAlchemy*'s or *Django*'s ones): a data specification class
(:class:`n6sdk.data_spec.DataSpec` or some subclass of it) looks like
an ORM "model" class and particular query parameter and result item
specifications (being instances of
:class:`n6sdk.data_spec.fields.Field` or of subclasses of it) are
declared similarly to ORM "fields" or "columns".

For example, consider the following simple data specification
class::

    class MyDataSpecFromScratch(n6sdk.data_spec.BaseDataSpec):

        id = UnicodeLimitedField(
            in_params='optional',
            in_result='required',
            max_length=64,
        )

        time = DateTimeField(
            in_params=None,
            in_result='required',

            extra_params=dict(
                min=DateTimeField(           # `time.min`
                    in_params='optional',
                    single_param=True,
                ),
                max=DateTimeField(           # `time.max`
                    in_params='optional',
                    single_param=True,
                ),
                until=DateTimeField(         # `time.until`
                    in_params='optional',
                    single_param=True,
                ),
            ),
        )

        address = AddressField(
            in_params=None,
            in_result='optional',
        )

        ip = IPv4Field(
            in_params='optional',
            in_result=None,

            extra_params=dict(
                net=IPv4NetField(            # `ip.net`
                    in_params='optional',
                ),
            ),
        )

        asn = ASNField(
            in_params='optional',
            in_result=None,
        )

        cc = CCField(
            in_params='optional',
            in_result=None,
        )

        count = IntegerField(
            in_params=None,
            in_result='optional',
            min_value=0,
            max_value=(2 ** 15 - 1),
        )


.. note::

   In a real project you should inherit from
   :class:`~n6sdk.data_spec.DataSpec` rather than from
   :class:`~n6sdk.data_spec.BaseDataSpec`.  See the following sections,
   especially :ref:`your_first_data_spec`.


What do we see in the above listing is that:

1. ``id`` is a text field: its values are strings, not longer than 64
   characters (as its declaration is an instance of
   :class:`n6sdk.data_spec.fields.UnicodeLimitedField` created with
   the constructor argument `max_length` set to ``64``). It is
   **optional** as a query parameter and **required** (obligatory) as
   an item of a result dictionary.

2. ``time`` is a date-and-time field (as its declaration is an
   instance of :class:`n6sdk.data_spec.fields.DateTimeField`). It is
   **not** a legal query parameter, and it is **required** as an item
   of a result dictionary.

3. ``time.min``, ``time.max`` and ``time.until`` are date-and-time
   fields (as their declarations are instances of
   :class:`n6sdk.data_spec.fields.DateTimeField`). They are
   **optional** as query parameters, and they are **not** legal items
   of a result dictionary.  Unlike most of other fields, these three
   fields do not allow to specify multiple query parameter values
   (note the constructor argument `single_param` set to :obj:`True`).

4. ``address`` is a field whose values are lists of dictionaries
   containing ``ip``, unique within a particular list of dictionaries,
   and optionally ``asn`` and ``cc`` (as the declaration of
   ``address`` is an instance of
   :class:`n6sdk.data_spec.fields.AddressField`). It is **not** a
   legal query parameter, and it is **optional** as an item of a
   result dictionary.

5. ``ip`` is an IPv4 address field (as its declaration is an instance
   of :class:`n6sdk.data_spec.fields.IPv4Field`). It is **optional**
   as a query parameter and it is **not** a legal item of a result
   dictionary (note that in a result dictionary the ``address`` field
   contains the corresponding data).

6. ``ip.net`` is an IPv4 network definition (as its declaration is an
   instance of :class:`n6sdk.data_spec.fields.IPv4NetField`). It is
   **optional** as a query parameter and it is **not** a legal item of
   a result dictionary.

7. ``asn`` is an autonomous system number (ASN) field (as its
   declaration is an instance of
   :class:`n6sdk.data_spec.fields.ASNField`). It is **optional** as a
   query parameter and it is **not** a legal item of a result
   dictionary (note that in a result dictionary the ``address`` field
   contains the corresponding data).

8. ``cc`` is 2-letter country code field (as its declaration is an
   instance of :class:`n6sdk.data_spec.fields.CCField`). It is
   **optional** as a query parameter and it is **not** a legal item of
   a result dictionary (note that in a result dictionary the
   ``address`` field contains the corresponding data).

9. ``count`` is an integer field: its values are integer numbers, not
   less than 0 and not greater than 32767 (as the declaration of
   ``count`` is an instance of
   :class:`n6sdk.data_spec.fields.IntegerField` created with the
   constructor arguments: `min_value` set to 0 and `max_value` set to
   32767).  It is **not** a legal query parameter, and it is
   **optional** as an item of a result dictionary.


To create your data specification class you will, most probably, want
to inherit from :class:`n6sdk.data_spec.DataSpec`.  In its subclass
you can:

* add new field specifications as well as modify (extend), replace
  (substitute) or remove (mask) field specifications defined in
  :class:`~n6sdk.data_spec.DataSpec`;

* extend the :class:`~n6sdk.data_spec.DataSpec`'s cleaning methods.

(See comments in ``Using_N6SDK/using_n6sdk/data_spec.py`` as well as
the :ref:`following <your_first_data_spec>` :ref:`sections
<more_on_data_spec>` of this tutorial.)

You may also want to subclass :class:`n6sdk.data_spec.fields.Field`
(or any of its subclasses, such as :class:`~.UnicodeLimitedField`,
:class:`~.IPv4Field` or :class:`~.IntegerField`) to create new kinds
of fields whose instances can be used as field specifications in your
data specification class (see :ref:`some portions
<custom_field_classes>` of the following sections of this
tutorial...).


.. _your_first_data_spec:

Your first data specification class
-----------------------------------

**Let us open the** ``<the workbench
directory>/Using_N6SDK/using_n6sdk/data_spec.py`` **file with our
favorite text editor and uncomment the following lines in it** (within
the body of the ``UsingN6sdkDataSpec`` class)::

    id = Ext(in_params='optional')

    source = Ext(in_params='optional')

    restriction = Ext(in_params='optional')

    confidence = Ext(in_params='optional')

    category = Ext(in_params='optional')

    time = Ext(
        extra_params=Ext(
            min=Ext(in_params='optional'),    # search for >= than...
            max=Ext(in_params='optional'),    # search for <= than...
            until=Ext(in_params='optional'),  # search for <  than...
        ),
    )

    ip = Ext(
        in_params='optional',
    )

    url = Ext(
        in_params='optional',
    )

Our ``UsingN6sdkDataSpec`` data specification class is a subclass of
:class:`n6sdk.data_spec.DataSpec` which, by default, has all query
parameters **disabled** -- so here we **enabled** *some* of them by
uncommenting these lines.  (We can remove the rest of commented
lines.)

.. note::

   You should always ensure that you *do not* enable in your *data
   specification class* any query parameters that are *not* supported
   by your *data backend API* (see: :ref:`data_backend_api`).

Apart from changing (extending) inherited field specifications, we can
also add some new fields.  For example, **let us add, near the
beginning of our data specification class definition, a new field
specification:** ``mac_address``.

::

    from n6sdk.data_spec import DataSpec, Ext
    from n6sdk.data_spec.fields import UnicodeRegexField  # remember to add this line


    class UsingN6sdkDataSpec(DataSpec):

        """
        The data specification class for the `Using_N6SDK` project.
        """

        mac_address = UnicodeRegexField(
            in_params='optional',  # *can* be in query params
            in_result='optional',  # *can* be in result data

            regex=r'^(?:[0-9A-F]{2}(?:[:-]|$)){6}$',
            error_msg_template=u'"{}" is not a valid MAC address',
        )

(Of course, we *do not remove* the lines uncommented earlier.)

If we need to get rid of some fields inherited from
:class:`~n6sdk.data_spec.DataSpec` -- then we can **just set them to**
:obj:`None`::

    class UsingN6sdkDataSpec(DataSpec):

        """
        The data specification class for the `Using_N6SDK` project.
        """

        action = None
        x509fp_sha1 = None

(Of course, we *do not remove* the lines uncommented and added
earlier.)


.. seealso::

   Please read :ref:`the apropriate subsection <extending_data_spec>`
   of the next section to learn more about adding, modifying,
   replacing and getting rid of particular fields.


.. _more_on_data_spec:

More on data specification
--------------------------

.. note::

   This section of the tutorial does not need to be read from the
   beginning to the end.  It is intended to be used as a guide to
   *data specification* and *field specification* classes, so please
   just check out the matter you are interested in.


.. _data_spec_cleaning_methods:

Data specification's cleaning methods
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The most important methods of any *data specification* (typically, an
instance of :class:`n6sdk.data_spec.DataSpec` or of its subclass) are:

* :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict` -- used to
  clean client query parameters;

* :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` -- used to
  clean results yielded by the data backend API.

Normally, these methods are called automatically by the *n6sdk*
machinery.

Each of these methods takes *exactly one positional argument* which is
respectively:

* for :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict` -- a
  **dictionary of query parameters** (representing one client
  request); the dictionary maps field names (query parameter names)
  to **lists of strings being their raw values** (lists -- because, as
  it was said, for most fields there can be more than one query
  parameter value);

* for :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` -- a
  **single result dictionary** (representing one network incident);
  the dictionary maps field names (result keys) to **their raw
  values** (not necessarily strings).

(Here "raw" is a synonym of "uncleaned".)

Each of these methods also accepts the following *optional keyword-only
arguments*:

* `ignored_keys` -- an iterable (e.g., a set or a list) of keys that
  will be completely ignored (i.e., the processed dictionary that has
  been given as the positional argument will be treated as it did not
  contain any of these keys; therefore, the resultant dictionary will
  not contain them either);

* `forbidden_keys` -- an iterable of keys that *must not apperar* in
  the processed dictionary;

* `extra_required_keys` -- an iterable of keys that *must appear* in
  the processed dictionary;

* `discarded_keys` -- an iterable of keys that will be removed
  (discarded) *after* validation of the processed dictionary keys (but
  *before* cleaning the values).

If a raw value is not valid and cannot be cleaned (see below:
:ref:`field_cleaning_methods`) or any other data specification
constraint is violated (including those specified with the
`forbidden_keys` and `extra_required_keys` arguments mentioned above)
an exception -- respectively: :exc:`.ParamKeyCleaningError` or
:exc:`.ParamValueCleaningError`, or :exc:`.ResultKeyCleaningError`, or
:exc:`.ResultValueCleaningError` -- is automatically raised.

Otherwise, *a new dictionary* is returned (the input dictionary given
as the positional argument *is not modified*).  Regarding returned
dictionaries:

* a dictionary returned by
  :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict` maps field
  names (query parameter names) to **lists of cleaned query parameter
  values** (not necessarily strings);

* a dictionary returned by
  :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` (containing
  cleaned data of exactly one network incident) maps field names
  (result keys) to **cleaned result values** (not necessarily strings).

The :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` method can
alternatively return :obj:`None` instead of a dictionary -- signalling
that this particular result dictionary, containing data of one network
incident, shall be skipped (i.e., the generated response will *not*
include data of this particular incident).  Note: although the *n6sdk*
machinery is prepared to handle such a case, the default
implementation of
:meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` never uses
this possibility (i.e., always returns a dictionary, not :obj:`None`).


.. _field_cleaning_methods:

Field specification's cleaning methods
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The most important methods of any *field* (an instance of
:class:`n6sdk.data_spec.fields.Field` or of its subclass) are:

* :meth:`~n6sdk.data_spec.fields.Field.clean_param_value` --
  called to clean a single query parameter value;

* :meth:`~n6sdk.data_spec.fields.Field.clean_result_value` --
  called to clean a single result value.

Each of these methods takes exactly *one positional argument*: a
single uncleaned (raw) value.

Each of these methods returns *a single value*: a cleaned one.

These methods are called by the data specification machinery in the
following way:

* The data specification's method
  :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict` (described
  above, in :ref:`data_spec_cleaning_methods`) calls the
  :meth:`~n6sdk.data_spec.fields.Field.clean_param_value` method of
  the appropriate field -- separately **for each element of each of
  the raw value lists taken from the dictionary passed as the
  argument**.

  If the field's method raises (or propagates) an exception being an
  instance/subclass of :exc:`~exceptions.Exception` (i.e., practically
  *any* exception, excluding :exc:`~exceptions.KeyboardInterrupt`,
  :exc:`~exceptions.SystemExit` and a few others), the data
  specification's method
  :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict` catches and
  collects it (doing the same for any such exceptions raised for other
  values, possibly for other fields) and then raises
  :exc:`.ParamValueCleaningError`.

  .. note::

     If the exception raised (or propagated) by the field's method is
     :exc:`.FieldValueError` (or any other exception derived from
     :exc:`._ErrorWithPublicMessageMixin`) its
     :attr:`~._ErrorWithPublicMessageMixin.public_message` will be
     included in the :exc:`.ParamValueCleaningError`'s
     :attr:`~.ParamValueCleaningError.public_message`).

* the data specification's method
  :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` (described
  above, in :ref:`data_spec_cleaning_methods`) calls the
  :meth:`~n6sdk.data_spec.fields.Field.clean_result_value` method of
  the appropriate field -- **for each raw value from the dictionary
  passed as the argument**.

  If the field's method raises (or propagates) an exception being an
  instance/subclass of :exc:`~exceptions.Exception` (i.e., practically
  *any* exception, excluding :exc:`~exceptions.KeyboardInterrupt`,
  :exc:`~exceptions.SystemExit` and a few others), the data
  specification's method
  :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` catches and
  collects it (doing the same for any such exceptions raised for other
  fields) and then raises :exc:`.ResultValueCleaningError`.

  .. note::

     Unlike :exc:`.ParamValueCleaningError` raised by
     :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict`, the
     :exc:`.ResultValueCleaningError` exception raised by
     :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` in
     reaction to exception(s) from
     :meth:`~n6sdk.data_spec.fields.Field.clean_result_value` *does
     not* include in its
     :attr:`~.ResultValueCleaningError.public_message` any information
     from the underlying exception(s) -- instead of that,
     :exc:`~.ResultValueCleaningError`\ 's
     :attr:`~.ResultValueCleaningError.public_message` is set to the
     safe default: ``u"Internal error."``.

     The rationale for this behaviour is that any exceptions related
     to *result cleaning* are strictly internal (contrary to those
     related to *query parameter cleaning*).

     Thanks to this behaviour, much of the code of field classes that
     is related to parameter value cleaning can be reused for result
     value cleaning without concern about disclosing some sensitive
     details in :attr:`~.ResultValueCleaningError.public_message` of
     :exc:`~.ResultValueCleaningError`.

     .. warning::

        For security sake, when extending data specification's
        :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` ensure
        that your implementation behaves the same way.


.. _data_spec_overview:

Overview of the basic data specification classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :class:`n6sdk.data_spec.DataSpec` and
:class:`n6sdk.data_spec.AllSearchableDataSpec` classes are two
variants of a base class for your own data specification class.

Each of them defines all standard *n6-like* REST API fields -- but:

* :class:`~n6sdk.data_spec.DataSpec` -- has *all query parameters*
  **disabled**.  This makes the class suitable for most *n6sdk* uses:
  in your subclass of :class:`~n6sdk.data_spec.DataSpec` you will
  *need to enable* (typically, with ``<field name> =
  Ext(in_params='optional')`` declarations) only those query
  parameters that your data backend supports.

* :class:`~n6sdk.data_spec.AllSearchableDataSpec` -- has *all query
  parameters* **enabled**.  This makes the class suitable for cases
  when your data backend supports all or most of standard *n6* query
  parameters.  In your subclass of
  :class:`~n6sdk.data_spec.AllSearchableDataSpec` you will need to
  *disable* (typically, with ``<field name> = Ext(in_params=None)``
  declarations) those query parameters that your data backend *does
  not* support.

The following list describes briefly all field specifications defined
in these two classes.

* basic event data fields:

    * ``id``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **required**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=64``
      * *param/result cleaning example:*

        * *raw value:* ``"abcDEF... \xc5\x81"``
        * *cleaned value:* ``u"abcDEF... \u0141"``

      Unique incident identifier being an arbitrary text.  Maximum
      length: 64 characters (after cleaning).

    * ``source``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **required**
      * *field class:* :class:`.SourceField`
      * *param/result cleaning example:*

        * *raw value:* ``"some-org.some-type"``
        * *cleaned value:* ``u"some-org.some-type"``

      Incident data source identifier. Consists of two parts separated
      with a dot (``.``). Allowed characters (apart from the dot) are:
      ASCII lower-case letters, digits and hyphen (``-``).  Maximum
      length: 32 characters (after cleaning).

    * ``restriction``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **required**
      * *field class:* :class:`.UnicodeEnumField`
      * *specific field constructor arguments:* ``enum_values=n6sdk.data_spec.RESTRICTION_ENUMS``
      * *param/result cleaning example:*

        * *raw value:* ``"public"``
        * *cleaned value:* ``u"public"``

      Data distribution restriction qualifier.  One of: ``"public"``,
      ``"need-to-know"`` or ``"internal"``.

    * ``confidence``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **required**
      * *field class:* :class:`.UnicodeEnumField`
      * *specific field constructor arguments:* ``enum_values=n6sdk.data_spec.CONFIDENCE_ENUMS``
      * *param/result cleaning example:*

        * *raw value:* ``"medium"``
        * *cleaned value:* ``u"medium"``

      Data confidence qualifier.  One of: ``"high"``, ``"medium"`` or
      ``"low"``.

    * ``category``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **required**
      * *field class:* :class:`.UnicodeEnumField`
      * *specific field constructor arguments:* ``enum_values=n6sdk.data_spec.CATEGORY_ENUMS``
      * *param/result cleaning example:*

        * *raw value:* ``"bots"``
        * *cleaned value:* ``u"bots"``

      Incident category label (some examples: ``"bots"``, ``"phish"``,
      ``"scanning"``...).

    * ``time``

      * *in params:* N/A
      * *in result:* **required**
      * *field class:* :class:`.DateTimeField`
      * *result cleaning examples:*

        * *example synonymous raw values:*

          *  ``"2014-11-05T23:13:00.000000"`` or
          *  ``"2014-11-06 01:13+02:00"`` or
          *  ``datetime.datetime(2014, 11, 5, 23, 13, 0)`` or
          *  ``datetime.datetime(2014, 11, 6, 1, 13, 0, 0, <tzinfo with UTC offset 2h>)``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      Incident *occurrence* time (**not**
      *when-entered-into-the-database*).  Value cleaning includes
      conversion to UTC time.

    * ``time.min``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``"2014-11-06T01:13+02:00"`` or
          * ``u"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The *earliest* time the queried incidents *occurred* at.  Value
      cleaning includes conversion to UTC time.

    * ``time.max``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"2014-11-06T01:13+02:00"`` or
          * ``"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The *latest* time the queried incidents *occurred* at.  Value
      cleaning includes conversion to UTC time.

    * ``time.until``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"2014-11-06T01:13+02:00"`` or
          * ``"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The time the queried incidents *occurred before* (i.e., exclusive; a
      handy replacement for ``time.max`` in some cases).  Value cleaning
      includes conversion to UTC time.

* ``address``-related fields:

    .. _field_spec_address:

    * ``address``

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.ExtendedAddressField`
      * *result cleaning examples:*

        * *example synonymous raw values:*

          * ``[{"ipv6": "::1"}, {"ip": "123.10.234.169", "asn": 999998}]`` or
          * ``[{u"ipv6": "::0001"}, {"ip": "123.10.234.169", u"asn": "999998"}]`` or
          * ``[{"ipv6": "0000:0000::0001"}, {u"ip": "123.10.234.169", u"asn": "15.16958"}]``

        * *cleaned value:* ``[{u"ipv6": u"::1"}, {u"ip": "123.10.234.169", u"asn": 999998}]``

      Set of network addresses related to the returned incident (e.g., for
      malicious web sites: taken from DNS *A* or *AAAA* records; for
      sinkhole/scanning: communication source addresses) -- in the form of
      a list of dictionaries, each containing:

      * obligatorily:

        * either ``"ip"`` (IPv4 address in quad-dotted decimal notation,
          cleaned using a subfield being an instance of
          :class:`.IPv4Field`)

        * or ``"ipv6"`` (IPv6 address in the standard text representation,
          cleaned using a subfield being an instance of
          :class:`.IPv6Field`)

        -- but *not* both ``"ip"`` and ``"ipv6"``;

      * plus optionally -- all or some of:

        * ``"asn"`` (autonomous system number in the form of a number or
          two numbers separated with a dot, cleaned using a subfield being
          an instance of :class:`.ASNField`),

        * ``"cc"`` (two-letter country code, cleaned using a subfield
          being an instance of :class:`.CCField`),

        * ``"dir"`` (the indicator of the address role in terms of the
          direction of the network flow in layers 3 or 4; one of:
          ``"src"``, ``"dst"``; cleaned using a subfield being an instance
          of :class:`.DirField`),

        * ``"rdns"`` (the domain name from the PTR record of the
          ``.in-addr-arpa`` domain associated with the IP address, without
          the trailing dot; cleaned using a subfield being an instance of
          :class:`.DomainNameField`).

      Values of ``ip`` and ``ipv6`` must be unique within the whole
      list.

      .. note::

         The cleaned IPv6 addresses is in the "condensed" form -- in
         contrast to the "exploded" form used for *param cleaning* of
         :ref:`ipv6 <field_spec_ipv6>` and :ref:`ipv6.net
         <field_spec_ipv6_net>`.

    * ``ip``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.IPv4Field`
      * *param cleaning example:*

        * *raw value:* ``"123.10.234.168"``
        * *cleaned value:* ``u"123.10.234.168"``

      IPv4 address (in quad-dotted decimal notation) related to the
      queried incidents.

    * ``ip.net``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.IPv4NetField`
      * *param cleaning example:*

        * *raw value:* ``"123.10.234.0/24"``
        * *cleaned value:* ``(u"123.10.234.0", 24)``

      IPv4 network (in CIDR notation) containing IP addresses related to
      the queried incidents.

    .. _field_spec_ipv6:

    * ``ipv6``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.IPv6Field`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"abcd::1"`` or
          * ``"ABCD::1"`` or
          * ``u"ABCD:0000:0000:0000:0000:0000:0000:0001"``
          * ``"abcd:0000:0000:0000:0000:0000:0000:0001"`` or

        * *cleaned value:* ``u"abcd:0000:0000:0000:0000:0000:0000:0001"``

      IPv6 address (in the standard text representation) related to the
      queried incidents.

      .. note::

         Cleaned values are in the "exploded" form -- in contrast to
         the "condensed" form used for *result cleaning* of
         :ref:`address <field_spec_address>`.

    .. _field_spec_ipv6_net:

    * ``ipv6.net``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.IPv6NetField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``"abcd::1/109"`` or
          * ``u"ABCD::1/109"`` or
          * ``"ABCD:0000:0000:0000:0000:0000:0000:0001/109"``
          * ``u"abcd:0000:0000:0000:0000:0000:0000:0001/109"`` or

        * *cleaned value:* ``(u"abcd:0000:0000:0000:0000:0000:0000:0001", 109)``

      IPv6 network (in CIDR notation) containing IPv6 addresses related to
      the queried incidents.

      .. note::

         The address part of each cleaned value is in the "exploded"
         form -- in contrast to the "condensed" form used for *result
         cleaning* of :ref:`address <field_spec_address>`.

    * ``asn``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.ASNField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"999998"`` or
          * ``u"15.16958"``

        * *cleaned value:* ``999998``

      Autonomous system number of IP addresses related to the queried
      incidents; in the form of a number or two numbers separated with a
      dot (see the examples above).

    * ``cc``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.CCField`
      * *param cleaning example:*

        * *raw value:* ``"US"``
        * *cleaned value:* ``u"US"``

      Two-letter country code related to IP addresses related to the
      queried incidents.

* fields related to *black list* events:

    * ``expires``:

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.DateTimeField`
      * *result cleaning examples:*

        * *example synonymous raw values:*

          *  ``"2014-11-05T23:13:00.000000"`` or
          *  ``"2014-11-06 01:13+02:00"`` or
          *  ``datetime.datetime(2014, 11, 5, 23, 13, 0)`` or
          *  ``datetime.datetime(2014, 11, 6, 1, 13, 0, 0, <tzinfo with UTC offset 2h>)``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      Black list item *expiry* time.  Value cleaning includes
      conversion to UTC time.

    * ``active.min``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``"2014-11-05T23:13:00.000000"`` or
          * ``"2014-11-06 01:13+02:00"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The *earliest* expiry-or-occurrence time of the queried black list
      items.  Value cleaning includes conversion to UTC time.

    * ``active.max``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"2014-11-05T23:13:00.000000"`` or
          * ``u"2014-11-06 01:13+02:00"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The *latest* expiry-or-occurrence time of the queried black list
      items.  Value cleaning includes conversion to UTC time.

    * ``active.until``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"2014-11-06T01:13+02:00"`` or
          * ``"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The time the queried incidents *expired or occurred before* (i.e.,
      exclusive; a handy replacement for ``active.max`` in some cases).
      Value cleaning includes conversion to UTC time.

    * ``replaces``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=64``
      * *param/result cleaning example:*

        * *raw value:* ``"abcDEF"``
        * *cleaned value:* ``u"abcDEF"``

      ``id`` of the black list item replaced by the queried/returned
      one.  Maximum length: 64 characters (after cleaning).

    * ``status``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeEnumField`
      * *specific field constructor arguments:* ``enum_values=n6sdk.data_spec.STATUS_ENUMS``
      * *param/result cleaning example:*

        * *raw value:* ``"active"``
        * *cleaned value:* ``u"active"``

      *Black list* item status qualifier.  One of: ``"active"`` (item
      currently in the list), ``"delisted"`` (item removed from the list),
      ``"expired"`` (item expired, so treated as removed by the n6 system)
      or ``"replaced"`` (e.g.: IP address changed for the same URL).

* fields related to *aggregated (high frequency)* events

    * ``count``:

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.IntegerField`
      * *specific field constructor arguments:* ``min_value=0, max_value=32767``
      * *result cleaning examples:*

        * *example synonymous raw values:* ``42`` or ``42.0`` or ``"42"``
        * *cleaned value:* ``42``

      Number of events represented by the returned incident data
      record.  It must be a positive integer number not greater
      than 32767.

    * ``until``:

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.DateTimeField`
      * *result cleaning examples:*

        * *example synonymous raw values:*

          *  ``"2014-11-05T23:13:00.000000"`` or
          *  ``"2014-11-06 01:13+02:00"`` or
          *  ``datetime.datetime(2014, 11, 5, 23, 13, 0)`` or
          *  ``datetime.datetime(2014, 11, 6, 1, 13, 0, 0, <tzinfo with UTC offset 2h>)``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The occurrence time of the *latest* [newest] aggregated event
      represented by the returned incident data record (*note:*
      ``time`` is the occurrence time of the *first* [oldest]
      aggregated event).  Value cleaning includes conversion to UTC
      time.

* the rest of the standard *n6* fields:

    * ``action``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=32``
      * *param/result cleaning example:*

        * *raw value:* ``"Some Text"``
        * *cleaned value:* ``u"Some Text"``

      Action taken by malware (e.g. ``"redirect"``, ``"screen
      grab"``...).  Maximum length: 32 characters (after cleaning).

    * ``adip``:

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.AnonymizedIPv4Field`
      * *result cleaning example:*

        * *raw value:* ``"x.X.234.168"``
        * *cleaned value:* ``u"x.x.234.168"``

      Anonymized destination IPv4 address: in quad-dotted decimal
      notation, with one or more segments replaced with ``"x"``, for
      example: ``"x.168.0.1"`` or ``"x.x.x.1"`` (*note:* at least the
      leftmost segment must be replaced with ``"x"``).

    * ``dip``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.IPv4Field`
      * *param/result cleaning example:*

        * *raw value:* ``"123.10.234.168"``
        * *cleaned value:* ``u"123.10.234.168"``

      Destination IPv4 address (for sinkhole, honeypot etc.; does not
      apply to malicious web sites) in quad-dotted decimal notation.

    * ``dport``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.PortField`
      * *param cleaning example:*

        * *raw value:* ``"80"``
        * *cleaned value:* ``80``

      * *result cleaning examples:*

        * *example synonymous raw values:* ``80`` or ``80.0`` or ``u"80"``
        * *cleaned value:* ``80``

      TCP/UDP destination port (non-negative integer number, less than
      65536).

    * ``email``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.EmailSimplifiedField`
      * *param/result cleaning example:*

        * *raw value:* ``"Foo@example.com"``
        * *cleaned value:* ``u"Foo@example.com"``

      E-mail address associated with the threat (e.g. source of spam,
      victim of a data leak).

    .. _field_spec_fqdn:

    * ``fqdn``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.DomainNameField`
      * *param/result cleaning examples:*

        * *example synonymous raw values:*

          * ``u"WWW.ŁÓDKA.ORG.EXAMPLE"`` or
          * ``"WWW.\xc5\x81\xc3\x93DKA.ORG.EXAMPLE"`` or
          * ``u"wwW.łódka.org.Example"`` or
          * ``"www.\xc5\x82\xc3\xb3dka.org.Example"`` or
          * ``u"www.xn--dka-fna80b.org.example"`` or
          * ``"www.xn--dka-fna80b.example.org"``

        * *cleaned value:* ``u"www.xn--dka-fna80b.example.org"``

      Fully qualified domain name related to the queried/returned
      incidents (e.g., for malicious web sites: from the site's URL; for
      sinkhole/scanning: the domain used for communication). Maximum
      length: 255 characters (after cleaning).

      .. note::

         During cleaning, the ``IDNA`` encoding is applied (see:
         https://docs.python.org/2.7/library/codecs.html#module-encodings.idna
         and http://en.wikipedia.org/wiki/Internationalized_domain_name;
         see also the above examples), then all remaining upper-case
         letters are converted to lower-case.

    * ``fqdn.sub``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.DomainNameSubstringField`
      * *param cleaning example:*

        * *raw value:* ``"mple.c"``
        * *cleaned value:* ``u"mple.c"``

      Substring of fully qualified domain names related to the queried
      incidents. Maximum length: 255 characters (after cleaning).

      .. seealso::

         See the above :ref:`fqdn <field_spec_fqdn>` description.

    * ``iban``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.IBANSimplifiedField`
      * *param/result cleaning example:*

        * *raw value:* ``"gB82weST12345698765432"``
        * *cleaned value:* ``u"GB82WEST12345698765432"``

      International Bank Account Number associated with fraudulent
      activity.

    * ``injects``:

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.ListOfDictsField`

      List of dictionaries containing data that describe a set of injects
      performed by banking trojans when a user loads a targeted website.
      (Exact structure of the dictionaries is dependent on malware family
      and not specified at this time.)

    * ``md5``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.MD5Field`
      * *param/result cleaning example:*

        * *raw value:* ``"b555773768bc1a672947d7f41f9c247f"``
        * *cleaned value:* ``u"b555773768bc1a672947d7f41f9c247f"``

      MD5 hash of the binary file related to the (queried/returned)
      incident.  In the form of a string of 32 hexadecimal digits.

    * ``modified``

      * *in params:* N/A
      * *in result:* **optional**
      * *field class:* :class:`.DateTimeField`
      * *result cleaning examples:*

        * *example synonymous raw values:*

          *  ``"2014-11-05T23:13:00.000000"`` or
          *  ``"2014-11-06 01:13+02:00"`` or
          *  ``datetime.datetime(2014, 11, 5, 23, 13, 0)`` or
          *  ``datetime.datetime(2014, 11, 6, 1, 13, 0, 0, <tzinfo with UTC offset 2h>)``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The time when the incident data was *made available through the API
      or modified*.  Value cleaning includes conversion to UTC time.

    * ``modified.min``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``"2014-11-06T01:13+02:00"`` or
          * ``u"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The *earliest* time the queried incidents were *made available
      through the API or modified* at.  Value cleaning includes conversion
      to UTC time.

    * ``modified.max``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"2014-11-06T01:13+02:00"`` or
          * ``"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The *latest* time the queried incidents were *made available through
      the API or modified* at.  Value cleaning includes conversion to UTC
      time.

    * ``modified.until``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`,
        marked as **single_param** in both
      * *in result:* N/A
      * *field class:* :class:`.DateTimeField`
      * *param cleaning examples:*

        * *example synonymous raw values:*

          * ``u"2014-11-06T01:13+02:00"`` or
          * ``"2014-11-05 23:13:00.000000"``

        * *cleaned value:* ``datetime.datetime(2014, 11, 5, 23, 13, 0)``

      The time the queried incidents were *made available through the API
      or modified* before (i.e., exclusive; a handy replacement for
      ``modified.max`` in some cases).  Value cleaning includes conversion
      to UTC time.

    * ``name``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=255``
      * *param/result cleaning example:*

        * *raw value:* ``"LoremIpsuM"``
        * *cleaned value:* ``u"LoremIpsuM"``

      Threat's exact name, such as ``"virut"``, ``"Potential SSH Scan"``
      or any other... Maximum length: 255 characters (after cleaning).

    * ``origin``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeEnumField`
      * *specific field constructor arguments:* ``enum_values=n6sdk.data_spec.ORIGIN_ENUMS``
      * *param/result cleaning example:*

        * *raw value:* ``"honeypot"``
        * *cleaned value:* ``u"honeypot"``

      Incident origin label (some examples: ``"p2p-crawler"``,
      ``"sinkhole"``, ``"honeypot"``...).

    * ``phone``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=20``

      Telephone number (national or international).  Maximum length:
      20 characters (after cleaning).

    * ``proto``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeEnumField`
      * *specific field constructor arguments:* ``enum_values=n6sdk.data_spec.PROTO_ENUMS``
      * *param/result cleaning example:*

        * *raw value:* ``"tcp"``
        * *cleaned value:* ``u"tcp"``

      Layer #4 protocol label -- one of: ``"tcp"``, ``"udp"``, ``"icmp"``.

    * ``registrar``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=100``

      Name of the domain registrar.  Maximum length: 100 characters
      (after cleaning).

    * ``sha1``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.SHA1Field`
      * *param/result cleaning example:*

        * *raw value:* ``u"7362d67c4f32ba5cd9096dcefc81b28ca04465b1"``
        * *cleaned value:* ``u"7362d67c4f32ba5cd9096dcefc81b28ca04465b1"``

      SHA-1 hash of the binary file related to the (queried/returned)
      incident.  In the form of a string of 40 hexadecimal digits.

    * ``sport``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.PortField`
      * *param cleaning example:*

        * *raw value:* ``u"80"``
        * *cleaned value:* ``80``

      * *result cleaning examples:*

        * *example synonymous raw values:* ``80`` or ``80.0`` or ``"80"``
        * *cleaned value:* ``80``

      TCP/UDP source port (non-negative integer number, less than 65536).

    * ``target``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=100``
      * *param/result cleaning example:*

        * *raw value:* ``"LoremIpsuM"``
        * *cleaned value:* ``u"LoremIpsuM"``

      Name of phishing target (organization, brand etc.). Maximum length:
      100 characters (after cleaning).

    .. _field_spec_url:

    * ``url``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.URLField`
      * *param/result cleaning examples:*

        * *example synonymous raw values:*

          * ``"ftp://example.com/non-utf8-\xdd"`` or
          * ``u"ftp://example.com/non-utf8-\udcdd"`` or
          * ``"ftp://example.com/non-utf8-\xed\xb3\x9d"``

        * *cleaned value:* ``u"ftp://example.com/non-utf8-\udcdd"``

      URL related to the queried/returned incidents. Maximum length: 2048
      characters (after cleaning).

      .. note::

         Cleaning involves decoding byte strings using the
         ``surrogateescape`` error handler backported from Python 3.x
         (see: :func:`n6sdk.encoding_helpers.provide_surrogateescape`).

    * ``url.sub``:

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* N/A
      * *field class:* :class:`.URLSubstringField`
      * *param cleaning example:*

        * *raw value:* ``"/example.c"``
        * *cleaned value:* ``u"/example.c"``

      Substring of URLs related to the queried incidents. Maximum length:
      2048 characters (after cleaning).

      .. seealso::

         See the above :ref:`url <field_spec_url>` description.

    * ``url_pattern``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:*
        ``max_length=255, disallow_empty=True``

      Wildcard pattern or regular expression triggering injects used
      by banking trojans.  Maximum length: 255 characters (after
      cleaning).

    * ``username``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.UnicodeLimitedField`
      * *specific field constructor arguments:* ``max_length=64``

      Local identifier (login) of the affected user.  Maximum length:
      64 characters (after cleaning).

    * ``x509fp_sha1``

      * *in params:*
        **optional** in :class:`~n6sdk.data_spec.AllSearchableDataSpec`,
        ``None`` in :class:`~n6sdk.data_spec.DataSpec`
      * *in result:* **optional**
      * *field class:* :class:`.SHA1Field`
      * *param/result cleaning example:*

        * *raw value:* ``u"7362d67c4f32ba5cd9096dcefc81b28ca04465b1"``
        * *cleaned value:* ``u"7362d67c4f32ba5cd9096dcefc81b28ca04465b1"``

      SHA-1 fingerprint of an SSL certificate.  In the form of a string of
      40 hexadecimal digits.

.. note::

   **Generally**, byte strings (if any), when converted to Unicode
   strings, are -- by default -- decoded using the ``utf-8`` encoding.


.. _extending_data_spec:

Adding, modifying, replacing and getting rid of particular fields...
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

As you already now, typically you create your own data specification
class by subclassing :class:`n6sdk.data_spec.DataSpec` or,
alternatively, :class:`n6sdk.data_spec.AllSearchableDataSpec`.

For variety's sake, this time we will subclass
:class:`~n6sdk.data_spec.AllSearchableDataSpec` (it has all relevant
fields marked as legal query parameters).

Let us prepare a temporary module for our experiments:

.. code-block:: bash

   $ cd <the workbench directory>/Using_N6SDK/using_n6sdk
   $ touch experimental_data_spec.py

Then, we can open the newly created file
(``experimental_data_spec.py``) with our favorite text editor and
place the following code in it::

    from n6sdk.data_spec import AllSearchableDataSpec
    from n6sdk.data_spec.fields import UnicodeEnumField

    class ExperimentalDataSpec(AllSearchableDataSpec):

        weekday = UnicodeEnumField(
            in_result='optional',
            enum_values=(
                'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                'Friday', 'Saturday', 'Sunday'),
            ),
        )

We just made a new *data specification class* -- very similar to
:class:`~n6sdk.data_spec.AllSearchableDataSpec` but with one
additional field specification: ``weekday``.

We could also modify (extend) within our subclass some of the field
specifications inherited from
:class:`~n6sdk.data_spec.AllSearchableDataSpec`.  For example::

    from n6sdk.data_spec import (
        AllSearchableDataSpec,
        Ext,
    )

    class ExperimentalDataSpec(AllSearchableDataSpec):
        # ...

        id = Ext(
            # here: changing the `max_length` property
            # of the `id` field -- from 64 to 32
            max_length=32,
        )
        time = Ext(
            # here: enabling bare `time` as a query parameter
            # (in AllSearchableDataSpec, by default, the `time.min`,
            # `time.max`, `time.until` query params are enabled but
            # bare `time` is not)
            in_params='optional',

            # here: making `time.min` a required query parameter
            # (*required* -- that is: a client *must* specify it
            # or they will get HTTP-400)
            extra_params=Ext(
                min=Ext(in_params='required'),
            ),
        )

Please note how :class:`n6sdk.data_spec.Ext` is used above to extend
existing (inherited) field specifications (see also: the
:ref:`your_first_data_spec` section).

It is also possible to replace existing (inherited) field
specifications with completely new definitions...

::

    # ...
    from n6sdk.data_spec.fields import MD5Field
    # ...

    class ExperimentalDataSpec(AllSearchableDataSpec):
        # ...
        id = MD5Field(
            in_params='optional',
            in_result='required',
        )
        # ...

...as well as to remove (mask) them::

    # ...
    class ExperimentalDataSpec(AllSearchableDataSpec):
        # ...
        count = None


You can also extend the
:meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict` and/or
:meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` method::

    # ...

    def _is_april_fools_day():
        now = datetime.datetime.utcnow()
        return now.month == 4 and now.day == 1


    class ExperimentalDataSpec(AllSearchableDataSpec):

        def clean_param_dict(self, params, ignored_keys=(), **kwargs):
            if _is_april_fools_day():
                ignored_keys = set(ignored_keys) | {'joke'}
            return super(ExperimentalDataSpec, self).clean_param_dict(
                params,
                ignored_keys=ignored_keys,
                **kwargs)

        def clean_result_dict(self, result, **kwargs):
            if _is_april_fools_day():
                result['time'] = '1810-03-01T13:13'
            return super(ExperimentalDataSpec, self).clean_result_dict(
                result,
                **kwargs)


.. note::

   Manipulating the optional keyword-only arguments (`ignored_keys`,
   `forbidden_keys`, `extra_required_keys`, `discarded_keys` -- see
   above: :ref:`data_spec_cleaning_methods`) of these methods can be
   useful, for example, when you need to implement some
   authentication-driven data anonymization or
   param/result-key-focused access rules (however, in such a case you
   may also need to add some additional keyword-only arguments to the
   signatures of these methods, e.g. `auth_data`; then you will also
   need to extend the :meth:`~.get_clean_param_dict_kwargs` and/or
   :meth:`~.get_clean_result_dict_kwargs` methods of your custom
   subclass of :class:`~.DefaultStreamViewBase`; generally that matter
   is beyond the scope of this tutorial).


.. _n6sdk_field_classes:

Standard field specification classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following list briefly describes all field classes defined in the
:mod:`n6sdk.data_spec.fields` module:

* :class:`~.Field`:

  The top-level base class for field specifications.

* :class:`~.DateTimeField`:

  * *base classes:* :class:`~.Field`
  * *raw (uncleaned) result value type:* :class:`str`/:class:`unicode`
    or :class:`datetime.datetime`
  * *cleaned value type:* :class:`datetime.datetime`
  * *example cleaned value:* ``datetime.datetime(2014, 11, 6, 13, 30, 1)``

  For date-and-time (timestamp) values, automatically normalized to
  UTC.

* :class:`~.FlagField`:

  * *base classes:* :class:`~.Field`
  * *example raw (uncleaned) param values:* ``""``, ``"1"``,
    ``"True"``, ``"TRUE"``, ``"true"``, ``"T"``, ``"t"``, ``"Yes"``,
    ``"YES"``, ``"yes"``, ``"Y"``, ``"y"``, ``"On"``, ``"ON"``,
    ``"on"``, ``"0"``, ``"False"``, ``"FALSE"``, ``"false"``, ``"F"``,
    ``"f"``, ``"No"``, ``"NO"``, ``"no"``, ``"N"``, ``"n"``,
    ``"Off"``, ``"OFF"``, ``"off"``...
  * *example raw (uncleaned) result values:* :obj:`True`,
    :obj:`False`, ``1``, ``0``, ``"1"``, ``"True"``, ``"TRUE"``,
    ``"true"``, ``"T"``, ``"t"``, ``"Yes"``, ``"YES"``, ``"yes"``,
    ``"Y"``, ``"y"``, ``"On"``, ``"ON"``, ``"on"``, ``"0"``,
    ``"False"``, ``"FALSE"``, ``"false"``, ``"F"``, ``"f"``, ``"No"``,
    ``"NO"``, ``"no"``, ``"N"``, ``"n"``, ``"Off"``, ``"OFF"``,
    ``"off"``...
  * *cleaned value type:* :class:`bool`
  * *the only possible cleaned values:* :obj:`True` or :obj:`False`

  For *YES/NO* (Boolean logic) flags, automatically converted to
  :class:`bool` (:obj:`True` or :obj:`False`).

  .. note::

     It is worth to note that a raw *param* value can be an empty
     string -- and that then the resultant cleaned value will be
     :obj:`True` (!).  Thanks to this rule, a flag can be set by
     specifying the apropriate URL query parameter with no value
     (i.e., by using just its name) -- e.g.:
     ``http://example.com/incidents.json?cc=PL&asn=123&someflag``
     (assuming we have in our data specification a
     :class:`~.FlagField` called *someflag*).

* :class:`~.UnicodeField`:

  * *base classes:* :class:`~.Field`
  * *most useful constructor arguments or subclass attributes:*

    * **encoding** (default: ``"utf-8"``)
    * **decode_error_handling** (default: ``"strict"``)
    * **disallow_empty** (default: :obj:`False`)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"Some text value. Zażółć gęślą jaźń."``

  For arbitrary text data.

* :class:`~.HexDigestField`:

  * *base classes:* :class:`~.UnicodeField`
  * **obligatory** *constructor arguments or subclass attributes:*

    * **num_of_characters** (exact number of characters)
    * **hash_algo_descr** (hash algorithm label, such as ``"MD5"`` or
      ``"SHA256"``...)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`

  For hexadecimal digests (hashes), such as *MD5*, *SHA256* or any
  other...

* :class:`~.MD5Field`:

  * *base classes:* :class:`~.HexDigestField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"b555773768bc1a672947d7f41f9c247f"``

  For hexadecimal MD5 digests (hashes).

* :class:`~.SHA1Field`:

  * *base classes:* :class:`~.HexDigestField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"7362d67c4f32ba5cd9096dcefc81b28ca04465b1"``

  For hexadecimal SHA-1 digests (hashes).

* :class:`~.UnicodeEnumField`:

  * *base classes:* :class:`~.UnicodeField`
  * **obligatory** *constructor arguments or subclass attributes:*

    * **enum_values** (a sequence or set of strings)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"Some selected text value"``

  For text data limited to a finite set of possible values.

* :class:`~.UnicodeLimitedField`:

  * *base classes:* :class:`~.UnicodeField`
  * **obligatory** *constructor arguments or subclass attributes:*

    * **max_length** (maximum number of characters)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"Some not-too-long text value"``

  For text data with limited length.

* :class:`~.UnicodeRegexField`:

  * *base classes:* :class:`~.UnicodeField`
  * **obligatory** *constructor arguments or subclass attributes:*

    * **regex** (regular expression -- as a string or compiled regular
      expression object)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"Some matching text value"``

  For text data limited by the specified regular expression.

* :class:`~.SourceField`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"some-organization.some-type"``

  For dot-separated source specifications, such as ``organization.type``.

* :class:`~.IPv4Field`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"123.10.234.168"``

  For IPv4 addresses (in decimal dotted-quad notation).

* :class:`~.IPv6Field`:

  * *base classes:* :class:`~.UnicodeField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned values:*

    * **cleaned param value:** ``u"abcd:0000:0000:0000:0000:0000:0000:0001``
      [note the "exploded" form]
    * **cleaned result value:** ``u"abcd::1"``
      [note the "condensed" form]

  For IPv6 addresses (in the standard text representation).

* :class:`~.AnonymizedIPv4Field`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"x.10.234.168"``

  For anonymized IPv4 addresses (in decimal dotted-quad notation, with
  the leftmost octet -- and possibly any other octets -- replaced
  with ``"x"``).

* :class:`~.IPv4NetField`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str`/:class:`unicode`
    or 2-:class:`tuple`: ``(<str/unicode>, <int>)``
  * *cleaned value types:*

    * **of cleaned param values:** 2-:class:`tuple`: ``(<unicode>, <int>)``
    * **of cleaned result values:** :class:`unicode`

  * *example cleaned values:*

    * **cleaned param value:** ``(u"123.10.0.0", 16)``
    * **cleaned result value:** ``u"123.10.0.0/16"``

  For IPv4 network specifications (in CIDR notation).

* :class:`~.IPv6NetField`:

  * *base classes:* :class:`~.UnicodeField`
  * *raw (uncleaned) result value type:* :class:`str`/:class:`unicode`
    or 2-:class:`tuple`: ``(<str/unicode>, <int>)``
  * *cleaned value types:*

    * **of cleaned param values:** 2-:class:`tuple`: ``(<unicode>, <int>)``
    * **of cleaned result values:** :class:`unicode`

  * *example cleaned values:*

    * **cleaned param value:** ``(u"abcd:0000:0000:0000:0000:0000:0000:0001", 109)``
      [note the "exploded" form of the address part]
    * **cleaned result value:** ``u"abcd::1/109"``
      [note the "condensed" form of the address part]

  For IPv6 network specifications (in CIDR notation).

* :class:`~.CCField`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"JP"``

  For 2-letter country codes.

* :class:`~.URLSubstringField`:

  * *base classes:* :class:`~.UnicodeLimitedField`
  * *most useful constructor arguments or subclass attributes:*

    * **decode_error_handling** (default: ``'surrogateescape'``)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"/xyz.example.c"``

  For substrings of URLs.

* :class:`~.URLField`:

  * *base classes:* :class:`~.URLSubstringField`
  * *most useful constructor arguments or subclass attributes:*

    * **decode_error_handling** (default: ``'surrogateescape'``)

  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"http://xyz.example.com/path?query=foo#bar"``

  For URLs.

* :class:`~.DomainNameSubstringField`:

  * *base classes:* :class:`~.UnicodeLimitedField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"xample.or"``

  For substrings of domain names, automatically IDNA-encoded and
  lower-cased.

* :class:`~.DomainNameField`:

  * *base classes:* :class:`~.DomainNameSubstringField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"www.xn--w-uga1v8h.example.org"``

  For domain names, automatically IDNA-encoded and lower-cased.

* :class:`~.EmailSimplifiedField`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"Foo@example.com"``

  For e-mail addresses (validation is rather rough).

* :class:`~.IBANSimplifiedField`:

  * *base classes:* :class:`~.UnicodeLimitedField`, :class:`~.UnicodeRegexField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *example cleaned value:* ``u"GB82WEST12345698765432"``

  For International Bank Account Numbers.

* :class:`~.IntegerField`:

  * *base classes:* :class:`~.Field`
  * *most useful constructor arguments or subclass attributes:*

    * **min_value** (*optional* minimum value)
    * **max_value** (*optional* maximum value)

  * *raw (uncleaned) result value type:* :class:`str`/:class:`unicode`
    or an **integer number** of *any numeric type*
  * *cleaned value type:* :class:`int` or (for bigger numbers) :class:`long`
  * *example cleaned value:* ``42``

  For integer numbers (optionally with minimum/maximum limits
  defined).

* :class:`~.ASNField`:

  * *base classes:* :class:`~.IntegerField`
  * *raw (uncleaned) result value type:* :class:`str`/:class:`unicode`
    or :class:`int`/:class:`long`
  * *cleaned value type:* :class:`int` or (possibly, for bigger numbers) :class:`long`
  * *example cleaned value:* ``123456789``

  For autonomous system numbers, such as ``12345`` or ``123456789``, or
  ``12345.65432``.

* :class:`~.PortField`:

  * *base classes:* :class:`~.IntegerField`
  * *raw (uncleaned) result value type:* :class:`str`/:class:`unicode`
    or an **integer number** of *any numeric type*
  * *cleaned value type:* :class:`int`
  * *example cleaned value:* ``12345``

  For TCP/UDP port numbers.

* :class:`~.ResultListFieldMixin`:

  * *base classes:* :class:`~.Field`
  * *most useful constructor arguments or subclass attributes:*

    * **allow_empty** (default: :obj:`False` which means that an empty
      sequence causes a cleaning error)

    * **sort_result_list** (default: :obj:`False`; if specified as
      :obj:`True` the :meth:`~list.sort` method will automatically be
      called on a resultant list; a :class:`collections.Mapping`
      instance can also be specified -- then it will be used as the
      dictionary of keyword arguments for each such :meth:`~list.sort`
      call)

  A mix-in class for fields whose result values are supposed to be a
  *sequence of values* and not single values.  Its
  :meth:`~.ResultListFieldMixin.clean_result_value` checks that its
  argument is a *non-string sequence* (:class:`list` or
  :class:`tuple`, or any other :class:`collections.Sequence` not being
  :class:`str` or :class:`unicode`) and performs result cleaning (as
  defined in a superclass) for *each item* of it.

  .. seealso::

     See the :ref:`ListOfDictsField <field_class_ListOfDictsField>`
     description below.

* :class:`~.DictResultField`:

  * *base classes:* :class:`~.Field`
  * *most useful constructor arguments or subclass attributes:*

    * **key_to_subfield_factory** (:obj:`None` or a dictionary that
      maps subfield keys to field classes or field factory functions
      -- see the :class:`~.DictResultField` documentation for
      details...)

  * *raw (uncleaned) result value type:* :class:`collections.Mapping`
  * *cleaned value type:* :class:`dict`

  A base class for fields whose result values are supposed to be
  dictionaries (their structure can be constrained by specifying the
  *key_to_subfield_factory* property -- see above).

  .. note::

     This is a result-only field class, i.e. its
     :meth:`~.DictResultField.clean_param_value` raises
     :exc:`~.exceptions.TypeError`.

  .. seealso::

     See the :ref:`ListOfDictsField <field_class_ListOfDictsField>`
     description below.

.. _field_class_ListOfDictsField:

* :class:`~.ListOfDictsField`:

  * *base classes:* :class:`~.ResultListFieldMixin`,
    :class:`~.DictResultField`
  * *most useful constructor arguments or subclass attributes:*

    * **must_be_unique** (an iterable container, empty by default,
      which specifies dictionary keys whose values must be unique
      within a particular list of dictionaries)
    * [see also superclasses' arguments/attributes]

  * *raw (uncleaned) result value type:* :class:`collections.Sequence`
    of :class:`collections.Mapping` instances
  * *cleaned value type:* :class:`list` of :class:`dict` instances
  * *example cleaned values:*

    * **cleaned param value:** N/A
      (:meth:`~.DictResultField.clean_param_value` raises
      :exc:`~.exceptions.TypeError`)
    * **cleaned result value:** ``[{u"a": u"b", u"c": 4, u"e": [1, 2, 3]}]``

  For lists of dictionaries containing arbitrary items.

  .. seealso::

     See the :ref:`AddressField <field_class_AddressField>` and
     :ref:`ExtendedAddressField <field_class_ExtendedAddressField>`
     descriptions below.

.. _field_class_AddressField:

* :class:`~.AddressField`:

  * *base classes:* :class:`~.ListOfDictsField`
  * *raw (uncleaned) result value type:* :class:`collections.Sequence`
    of :class:`collections.Mapping` instances
  * *cleaned value type:* :class:`list` of :class:`dict` instances
  * *example cleaned values:*

    * **cleaned param value:** N/A
      (:meth:`~.DictResultField.clean_param_value` raises
      :exc:`~.exceptions.TypeError`)
    * **cleaned result value:** ``[{u"ip": u"123.10.234.169", u"cc":
      u"UA", u"asn": 12345}]``

  For lists of dictionaries -- each containing unique ``"ip"`` and
  optionally ``"cc"`` and/or ``"asn"``.

* :class:`~.DirField`:

  * *base classes:* :class:`~.UnicodeEnumField`
  * *raw (uncleaned) result value type:* :class:`str` or :class:`unicode`
  * *cleaned value type:* :class:`unicode`
  * *the only possible cleaned values:* ``u"src"`` or ``u"dst"``

  For ``dir`` values in items cleaned by of
  :class:`ExtendedAddressField` instances (``dir`` marks role of the
  address in terms of the direction of the network flow in layers 3 or
  4).

.. _field_class_ExtendedAddressField:

* :class:`~.ExtendedAddressField`:

  * *base classes:* :class:`~.ListOfDictsField`
  * *raw (uncleaned) result value type:* :class:`collections.Sequence`
    of :class:`collections.Mapping` instances
  * *cleaned value type:* :class:`list` of :class:`dict` instances
  * *example cleaned values:*

    * **cleaned param value:** N/A
      (:meth:`~.DictResultField.clean_param_value` raises
      :exc:`~.exceptions.TypeError`)
    * **cleaned result value:** ``[{u"ipv6": u"abcd::1", u"cc": u"PL",
      u"asn": 12345, u"dir": u"dst"}]``

  For lists of dictionaries -- each containing either ``"ip"`` or
  ``"ipv6"`` (but not both; each must be unique within the whole
  list), and optionally all or some of: ``"cc"``, ``"asn"``,
  ``"dir"``, ``"rdns"``.


.. note::

   **Generally --**

   * constructor arguments, when specified, must be provided as
     *keyword arguments*;
   * "constructor argument or subclass attribute" means that a certain
     field property can be specified in two alternative ways: either
     when creating a field instance (specifying the property as the
     corresponding keyword argument passed in to the constructor) or
     when subclassing the field class (overriding the corresponding
     class-level attribute in the subclass definition; see below:
     :ref:`custom_field_classes`);
   * raw (uncleaned) *parameter* value type is *always*
     :class:`str`/:class:`unicode`;
   * all these classes are *cooperative-inheritance*-friendly (i.e.,
     :func:`super` in subclasses' :meth:`clean_param_value` and
     :meth:`clean_result_value` will work properly, also with multiple
     inheritance).


.. seealso::

   See above: :ref:`data_spec_overview`.


.. _custom_field_classes:

Custom field specification classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You may want to subclass any of the *n6sdk* field classes (described
above, in :ref:`n6sdk_field_classes`):

* to override some class-level attributes,

* to extend the
  :meth:`~n6sdk.data_spec.fields.Field.clean_param_value` and/or
  :meth:`~n6sdk.data_spec.fields.Field.clean_result_value` method (see
  above: :ref:`field_cleaning_methods`).

Please, consider the beginning of our ``<the workbench
directory>/Using_N6SDK/using_n6sdk/data_spec.py`` file::

    from n6sdk.data_spec import DataSpec, Ext
    from n6sdk.data_spec.fields import UnicodeRegexField


    class UsingN6sdkDataSpec(DataSpec):

        """
        The data specification class for the `Using_N6SDK` project.
        """

        mac_address = UnicodeRegexField(
            in_params='optional',  # *can* be in query params
            in_result='optional',  # *can* be in result data

            regex=r'^(?:[0-9A-F]{2}(?:[:-]|$)){6}$',
            error_msg_template=u'"{}" is not a valid MAC address',
        )

It can be rewritten in a more self-documenting and
code-reusability-friendly way::

    from n6sdk.data_spec import DataSpec, Ext
    from n6sdk.data_spec.fields import UnicodeRegexField


    class MacAddressField(UnicodeRegexField):

        regex = r'^(?:[0-9A-F]{2}(?:[:-]|$)){6}$'
        error_msg_template = u'"{}" is not a valid MAC address'


    class UsingN6sdkDataSpec(DataSpec):

        """
        The data specification class for the `Using_N6SDK` project.
        """

        mac_address = MacAddressField(
            in_params='optional',  # *can* be in query params
            in_result='optional',  # *can* be in result data
        )

The other technique -- extending the value cleaning methods -- offers
more possibilities.  For example, we could create an integer number
field that accepts parameter values with such suffixes as ``"m"``
(*meters*), ``"kg"`` (*kilograms*) and ``"s"`` (*seconds*), and
ignores those suffixes::

    from n6sdk.data_spec.fields import IntegerField

    class SuffixedIntegerField(IntegerField):

        # the `legal_suffixes` class attribute we create here
        # can be overridden with a `legal_suffixes` constructor
        # argument or a `legal_suffixes` subclass attribute
        legal_suffixes = 'm', 'kg', 's'

        def clean_param_value(self, value):
            """
            >>> SuffixedIntegerField().clean_param_value('123 kg')
            123
            """
            value = value.strip()
            for suffix in self.legal_suffixes:
                if value.endswith(suffix):
                    value = value[:(-len(suffix))]
                    break
            value = super(SuffixedIntegerField,   # string to int...
                          self).clean_param_value(value)
            return value

If -- in your implementation of
:meth:`~n6sdk.data_spec.fields.Field.clean_param_value` or
:meth:`~n6sdk.data_spec.fields.Field.clean_result_value` -- you need
to raise a cleaning error (to signal that a value is invalid and
cannot be cleaned) just raise any exception being an instance of
standard :exc:`~exceptions.Exception` (or of its subclass); it *can*
(but *does not have to*) be :exc:`n6sdk.exceptions.FieldValueError`.

When subclassing *n6sdk* field classes, please do not be afraid to
look into the source code of the :mod:`n6sdk.data_spec.fields` module.


.. _data_backend_api:

Implementing the data backend API
=================================

.. _data_backend_api_interface:

The interface
-------------

The network incident data can be stored in various ways: using text
files, in an SQL database, using some distributed storage such as
Hadoop etc.  Implementation of obtaining data from any of such
backends is beyond the scope of this document.  What we do concern
here is the API the *n6sdk*'s machinery uses to get the data.

Therefore, for the purposes of this tutorial, we will assume that our
network incident data is stored in the simplest possible way: *in one
file, in the JSON format*.  You will have to replace any
implementation details related to this particular way of keeping data
and querying for data with an implementation appropriate for the data
store you use (file reads, SQL queries or whatever is needed for the
particular storage backend) -- see the next section:
:ref:`implementation_guidelines`.

First, we will **create the example JSON data file**:

.. code-block:: bash

   $ cat << EOF > /tmp/our-data.json
        [
          {
            "id": "1", 
            "address": [
              {
                "ip": "11.22.33.44"
              }, 
              {
                "asn": 12345, 
                "cc": "US", 
                "ip": "123.124.125.126"
              }
            ], 
            "category": "phish", 
            "confidence": "low", 
            "mac_address": "00:11:22:33:44:55", 
            "restriction": "public", 
            "source": "test.first", 
            "time": "2015-04-01 10:00:00", 
            "url": "http://example.com/?spam=ham"
          }, 
          {
            "id": "2", 
            "adip": "x.2.3.4", 
            "category": "server-exploit", 
            "confidence": "medium", 
            "restriction": "need-to-know", 
            "source": "test.first", 
            "time": "2015-04-01 23:59:59"
          }, 
          {
            "id": "3", 
            "address": [
              {
                "ip": "11.22.33.44"
              }, 
              {
                "asn": 87654321, 
                "cc": "PL", 
                "ip": "111.122.133.144"
              }
            ], 
            "category": "server-exploit", 
            "confidence": "high", 
            "restriction": "public", 
            "source": "test.second", 
            "time": "2015-04-01 23:59:59", 
            "url": "http://example.com/?spam=ham"
          }
        ]
   EOF

Then, we need to **open the file** ``<the workbench
directory>/Using_N6SDK/using_n6sdk/data_backend_api.py`` with our
favorite text editor and **modify it so that it will contain the
following code** (however, it is recommented not to remove the
comments and docstrings the file already contains -- as they can be
valuable hints for future code maintainers)::

    import json

    from n6sdk.class_helpers import singleton
    from n6sdk.datetime_helpers import parse_iso_datetime_to_utc
    from n6sdk.exceptions import AuthorizationError


    @singleton
    class DataBackendAPI(object):

        def __init__(self, settings):
            ## [...existing docstring + comments...]
            # Implementation for our example JSON-file-based "storage":
            with open(settings['json_data_file_path']) as f:
                self.data = json.load(f)

        ## [...existing comments...]

        def generate_incidents(self, auth_data, params):
            ## [...existing docstring + comments...]
            # This is a naive implementation for our example
            # JSON-file-based "storage" (some efficient database
            # query needs to be performed instead, in case of any
            # real-world implementation...):
            for incident in self.data:
                for key, value_list in params.items():
                    if key == 'ip':
                        address_seq = incident.get('address', [])
                        if not any(addr.get(key) in value_list
                                   for addr in address_seq):
                            break   # incident does not match the query params
                    elif key in ('time.min', 'time.max', 'time.until'):
                        [param_val] = value_list  # must be exactly one value
                        db_val = parse_iso_datetime_to_utc(incident['time'])
                        if not ((key == 'time.min' and db_val >= param_val) or
                                (key == 'time.max' and db_val <= param_val) or
                                (key == 'time.until' and db_val < param_val)):
                            break   # incident does not match the query params
                    elif incident.get(key) not in value_list:
                        break       # incident does not match the query params
                else:
                    # (the inner for loop has not been broken)
                    yield incident  # incident *matches* the query params

What is important:

1. The constructor of the class is supposed to be called exactly once
   per application run. The constructor must take exactly one
   argument:

   * `settings` -- a dictionary containing settings from the ``*.ini``
     file (e.g., ``development.ini`` or ``production.ini``).

2. The class can have one or more data query methods, with arbitrary
   names (in the above example there is only one:
   :func:`generate_incidents`; to learn how URLs are mapped to
   particular data query method names -- see below:
   :ref:`gluing_it_together`).

   Each data query method must take two positional arguments:

   * `auth_data` -- authentication data, relevant only if you need to
     implement in your data query methods some kind of authorization
     based on the authentication data; its type and format depends on
     the authentication policy you use (see below:
     :ref:`custom_authn_policy`);
   * `params` -- a dictionary containing already cleaned (validated
     and normalized with
     :meth:`~n6sdk.data_spec.BaseDataSpec.clean_param_dict`) client
     query parameters; the dictionary maps parameter names (strings)
     to lists of cleaned parameter values (see above:
     :ref:`data_spec_class`).

3. Each data query method must be a *generator* (see:
   https://docs.python.org/2/glossary.html#term-generator) or any
   other callable that returns an *iterator* (see:
   https://docs.python.org/2/glossary.html#term-iterator). Each of the
   generated items should be a dictionary containing the data of one
   network incident (the *n6sdk* machinery will use it as the argument
   for the :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict`
   data specification method).


.. _implementation_guidelines:

Guidelines for the real implementation
--------------------------------------

Typically, the following activities are performed **in the __init__()
method** of the data backend API class:

1. Get the storage backend settings from the `settings` dictionary
   (apropriate items should have been placed in the ``[app:main]``
   section of the ``*.ini`` file -- see below:
   :ref:`gluing_it_together`).

2. Configure the storage backend (for example, create the database
   connection).

Typically, the following activities are performed **in a data query
method** of the data backend API class:

1. If needed: do any authorization checks based on the `auth_data` and
   `params` arguments; raise
   :exc:`n6sdk.exceptions.AuthorizationError` on failure.

2. Translate the contents of the `params` argument to some
   storage-specific queries. (Obviously, when doing the translation
   you may need, for example, to map `params` keys to some
   storage-specific keys...).

   .. note::

      If the data specification includes dotted "extra params" (such
      as ``time.min``, ``time.max``, ``time.until``, ``fqdn.sub``,
      ``ip.net`` etc.) their semantics should be implemented
      carefully.

3. If needed: perform a necessary storage-specific maintenance
   activity (e.g., re-new the database connection).

4. Perform a storage-specific query (or queries).

   Sometimes you may want to limit the number of allowed results --
   then, raise :exc:`n6sdk.exceptions.TooMuchDataError` if the limit
   is exceeded.

5. Translate the results of the storage-specific query (queries) to
   result dictionaries and *yield* each of these dictionaries (each of
   them should be a dictionary ready to be passed to the
   :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` data
   specification method).

   (Obviously, when doing the translation, you may need, for example,
   to map some storage-specific keys to the result keys accepted by
   the :meth:`~n6sdk.data_spec.BaseDataSpec.clean_result_dict` method
   of your data specificaton class...)

   If there are no results -- just do not yield any items (the caller
   will obtain an empty iterator).

In case of an internal error, do not be afraid to raise an exception
-- any instance of :exc:`~exceptions.Exception` (or of its subclass)
will be handled automatically by the *n6sdk* machinery: logged
(including the traceback) using the ``n6sdk.pyramid_commons`` logger
and transformed into :exc:`pyramid.httpexceptions.HTTPServerError`
which will break generation of the HTTP response body (note, however,
that there will be no *HTTP-500* response -- because of the "pipeline"
nature of the whole process: it is not possible to send an "error
response" when some parts of the body of the "data response" have
already been sent out).

It is recommended to decorate your data backend API class with the
:func:`n6sdk.class_helpers.singleton` decorator (it ensures that the
class is instantiated only once; any attempt to repeat that causes
:exc:`~.exceptions.TypeError`).


.. _custom_authn_policy:

Custom authentication policy
============================

A description of the concept of *Pyramid authentication policies* is
beyond the scope of this tutorial.  Unless you need something more
sophisticated than the dummy
:class:`~n6sdk.pyramid_commons.AnonymousAuthenticationPolicy` you can
skip to :ref:`the next chapter <gluing_it_together>` of this tutorial.

Otherwise, please read the appropriate portion and example from the
documentation of the *Pyramid* library:
http://docs.pylonsproject.org/projects/pyramid/en/1.5-branch/narr/security.html#creating-your-own-authentication-policy
(you may also want to search the *Pyramid* documentation for the term
``authentication policy``) as well as the following paragraphs.

The *n6sdk* library requires that the authentication policy class has
the additional static (decorated with :func:`staticmethod`) method
:meth:`get_auth_data` that takes exactly one positional argument: a
*Pyramid request* object.  The method is expected to return a value
that is **not** :obj:`None` in case of authentication success, and
:obj:`None` otherwise.  Apart from this simple rule there are no
constraints what exactly the return value should be -- the implementer
decides about that.  The return value will be available as the
:obj:`auth_data` attribute of the *Pyramid request* as well as is
passed into data backend API methods as the `auth_data` argument.

Typically, the :meth:`authenticated_userid` method implementation
makes use of the request's attribute :obj:`auth_data` (being return
value of :meth:`get_auth_data`), and the :meth:`get_auth_data`
implementation makes some use of the request's attribute
:obj:`unauthenticated_userid` (being return value of the
:meth:`unauthenticated_userid` policy method).  It is possible because
:meth:`get_auth_data` is called (by the *Pyramid* machinery) *after*
the :meth:`unauthenticated_userid` method and *before* the
:meth:`authenticated_userid` method.

The *n6sdk* library provides
:class:`n6sdk.pyramid_commons.BaseAuthenticationPolicy` -- an
authentication policy base class that makes it easier to implement
your own authentication policies.  Please consult its source code.


.. _gluing_it_together:

Gluing it together
==================

We can inspect the ``__init__.py`` file of our application (``<the
workbench directory>/Using_N6SDK/using_n6sdk/__init__.py``) with our
favorite text editor.  It contains a lot of useful comments that
suggest how to customize the code -- however, if we omitted them, the
actual Python code would be::

    from n6sdk.pyramid_commons import (
        AnonymousAuthenticationPolicy,
        ConfigHelper,
        HttpResource,
    )

    from .data_spec import UsingN6sdkDataSpec
    from .data_backend_api import DataBackendAPI


    # (this is how we map URLs to particular data query methods...)
    RESOURCES = [
        HttpResource(
            resource_id='/incidents',
            url_pattern='/incidents.{renderer}',
            view_properties=dict(
                data_spec=UsingN6sdkDataSpec(),
                data_backend_api_method='generate_incidents',
                renderers=('json', 'sjson'),
            ),
        ),
    ]


    def main(global_config, **settings):
        helper = ConfigHelper(
            settings=settings,
            data_backend_api_class=DataBackendAPI,
            authentication_policy=AnonymousAuthenticationPolicy(),
            resources=RESOURCES,
        )
        return helper.make_wsgi_app()

(In the context of descriptions the previous portions of the tutorial
contain, this boilerplate code should be rather self-explanatory.  If
not, please consult the comments in the actual ``<the workbench
directory>/Using_N6SDK/using_n6sdk/__init__.py`` file.)

Now, yet another important step needs to be completed: **customization
of the settings** in the ``<the workbench
directory>/Using_N6SDK/*.ini`` files: ``development.ini`` and
``production.ini`` -- to match the environment, database configuration
(if any) etc.

.. warning::

   You should **not** place any sensitive settings (such as real
   database passwords) in these files -- as they are still just
   configuration templates (which your will want, for example, to add
   to your version control system) and **not** real configuration
   files for production.

   .. seealso::

      See below: :ref:`prod_install`.

In case of our naive JSON-file-based data backend implementation (see
above: :ref:`data_backend_api_interface`) we need to **add the
following line in the** ``[app:main]`` **section of each of the two
settings files** (``development.ini`` and ``production.ini``):

.. code-block:: ini

   json_data_file_path = /tmp/our-data.json

Finally, let us run the application (still in the development
environment):

.. code-block:: bash

   $ cd <the workbench directory>
   $ source dev-venv/bin/activate   # ensuring the virtualenv is active
   $ pserve Using_N6SDK/development.ini

Our application should be being served now.  Try visiting the
following URLs (with any web browser or, for example, with the
``wget`` command-line tool):

* ``http://127.0.0.1:6543/incidents.json``
* ``http://127.0.0.1:6543/incidents.json?ip=11.22.33.44``
* ``http://127.0.0.1:6543/incidents.json?ip=11.22.33.44&time.min=2015-04-01T23:00:00``
* ``http://127.0.0.1:6543/incidents.json?category=phish``
* ``http://127.0.0.1:6543/incidents.json?category=server-exploit``
* ``http://127.0.0.1:6543/incidents.json?category=server-exploit&ip=11.22.33.44``
* ``http://127.0.0.1:6543/incidents.json?category=bots&category=server-exploit``
* ``http://127.0.0.1:6543/incidents.json?category=bots,dos-attacker,phish,server-exploit``
* ``http://127.0.0.1:6543/incidents.sjson?mac_address=00:11:22:33:44:55``
* ``http://127.0.0.1:6543/incidents.sjson?source=test.first``
* ``http://127.0.0.1:6543/incidents.sjson?source=test.second``
* ``http://127.0.0.1:6543/incidents.sjson?source=some.non-existent``
* ``http://127.0.0.1:6543/incidents.sjson?source=some.non-existent&source=test.second``
* ``http://127.0.0.1:6543/incidents.sjson?time.min=2015-04-01T23:00``
* ``http://127.0.0.1:6543/incidents.sjson?time.max=2015-04-01T23:59:59&confidence=medium,low``
* ``http://127.0.0.1:6543/incidents.sjson?time.until=2015-04-01T23:59:59``

...as well as those causing (expected) errors:

* ``http://127.0.0.1:6543/incidents``
* ``http://127.0.0.1:6543/incidents.jsonnn``
* ``http://127.0.0.1:6543/incidents.json?some-illegal-key=1&another-one=foo``
* ``http://127.0.0.1:6543/incidents.json?category=wrong``
* ``http://127.0.0.1:6543/incidents.json?category=bots,wrong``
* ``http://127.0.0.1:6543/incidents.json?category=bots&category=wrong``
* ``http://127.0.0.1:6543/incidents.json?ip=11.22.33.44.55``
* ``http://127.0.0.1:6543/incidents.sjson?mac_address=00:11:123456:33:44:55``
* ``http://127.0.0.1:6543/incidents.sjson?time.min=2015-04-01T23:00,2015-04-01T23:30``
* ``http://127.0.0.1:6543/incidents.sjson?time.min=2015-04-01T23:00&time.min=2015-04-01T23:30``
* ``http://127.0.0.1:6543/incidents.sjson?time.min=blablabla``
* ``http://127.0.0.1:6543/incidents.sjson?time.max=blablabla&ip=11.22.33.444``
* ``http://127.0.0.1:6543/incidents.sjson?time.until=2015-04-01T23:59:59&ip=11.22.33.444``

Now, it can be a good idea to try the :ref:`helper script for
automatized basic API testing <n6sdk_api_test_tool>`.


.. _prod_install:

Installation for production (using Apache server)
=================================================

.. warning::

   The content of this chapter is intended to be a brief and rough
   explanation of how you can glue relevant configuration stuff
   together.  It is **not** intended to be used as a step-by-step
   recipe for a secure production configuration.  **The final
   configuration (including but not limited to file access
   permissions) should always be carefully reviewed by an experienced
   system administrator -- BEFORE it is deployed on a publicly
   available server**.

Prerequisites are similar to those concerning the development
environment, listed near the beginning of this tutorial.  The same
applies to the way of obtaining the source code of *n6sdk*.

.. seealso::

   See the sections: :ref:`working_env_prerequisites` and
   :ref:`obtaining_source_code`.

The Debian GNU/Linux operating system in the version 7.11 or newer
is recommended to follow the guides presented below.  Additional
prerequisite is that the Apache2 HTTP server is installed and
configured together with ``mod_wsgi`` (the ``apache2`` and
``libapache2-mod-wsgi`` Debian packages).

First, we will create a directory structure and a *virtualenv* for our
server -- e.g., under ``/opt``:

.. code-block:: bash

   $ sudo mkdir /opt/myn6-srv
   $ cd /opt/myn6-srv
   $ sudo virtualenv prod-venv
   $ sudo chown -R $(echo $USER) prod-venv
   $ deactivate  # ensure no virtualenv is active
   $ source prod-venv/bin/activate  # activate the production virtualenv

Then, let us install the necessary packages:

.. code-block:: bash

   $ cd <the workbench directory>/n6sdk
   $ python setup.py install
   $ cd <the workbench directory>/Using_N6SDK
   $ python setup.py install

(Of course, ``<the workbench directory>/n6sdk`` needs to be replaced
with the actual name (absolute path) of the directory containing the
source code of the *n6sdk* library; and ``<the workbench
directory>/Using_N6SDK`` needs to be replaced with the actual name
(absolute path) of the directory containing the source code of our
*n6sdk*-based project.)

Now, we will copy the template of the configuration file for
production:

.. code-block:: bash

    $ cd /opt/myn6-srv
    $ sudo cp <the workbench directory>/Using_N6SDK/production.ini ./

For security sake, let us restrict access to the ``production.ini``
file before we will place any real passwords and other sensitive
settings in it:

.. code-block:: bash

    $ sudo chown root ./production.ini
    $ sudo chmod 600 ./production.ini

We need to ensure that the Apache's user group has read-only access to
the file.  On Debian GNU/Linux it can be done by executing:

.. code-block:: bash

    $ sudo chgrp www-data ./production.ini
    $ sudo chmod g+r ./production.ini

You may want to customize the settings that the file contains,
especially to match your production environment, database
configuration etc.  Just edit the ``/opt/myn6-srv/production.ini``
file.

Then, we will create the WSGI script:

.. code-block:: bash

    $ cat << EOF > prod-venv/myn6-app.wsgi
    from pyramid.paster import get_app, setup_logging
    ini_path = '/opt/myn6-srv/production.ini'
    setup_logging(ini_path)
    application = get_app(ini_path, 'main')
    EOF

...and provide the directory for the *egg cache*:

.. code-block:: bash

    $ sudo mkdir /opt/myn6-srv/.python-eggs

We need to ensure that the Apache's user has write access to it.  On
Debian GNU/Linux it can be done by executing:

.. code-block:: bash

    $ sudo chown www-data /opt/myn6-srv/.python-eggs
    $ sudo chmod 755 /opt/myn6-srv/.python-eggs

Now, we need to adjust the Apache configuration.  On Debian GNU/Linux
it can be done by executing the following shell commands:

.. code-block:: bash

    $ cat << EOF > prod-venv/myn6.apache
    <VirtualHost *:80>
      # Only one Python sub-interpreter should be used
      # (multiple ones do not cooperate well with C extensions).
      WSGIApplicationGroup %{GLOBAL}

      # Remove the following line if you use native Apache authorization.
      WSGIPassAuthorization On

      # See the description of WSGIDaemonProcess on the modwsgi wiki page:
      # https://modwsgi.readthedocs.io/en/develop/configuration-directives/WSGIDaemonProcess.html
      WSGIDaemonProcess myn6_srv \\
        python-path=/opt/myn6-srv/prod-venv/lib/python2.7/site-packages \\
        python-eggs=/opt/myn6-srv/.python-eggs
      WSGIScriptAlias /myn6 /opt/myn6-srv/prod-venv/myn6-app.wsgi

      <Directory /opt/myn6-srv/prod-venv>
        WSGIProcessGroup myn6_srv
        Order allow,deny
        Allow from all
      </Directory>

      # Logging of errors and other events:
      ErrorLog \${APACHE_LOG_DIR}/error.log
      # Possible values for the LogLevel directive include:
      # debug, info, notice, warn, error, crit, alert, emerg.
      LogLevel warn

      # Logging of client requests:
      CustomLog \${APACHE_LOG_DIR}/access.log combined

      # It is recommended to uncomment and adjust the following line.
      #ServerAdmin webmaster@yourserver.example.com
    </VirtualHost>
    EOF
    $ sudo chmod 640 prod-venv/myn6.apache
    $ sudo chown root:root prod-venv/myn6.apache
    $ sudo mv prod-venv/myn6.apache /etc/apache2/sites-available/myn6
    $ cd /etc/apache2/sites-enabled
    $ sudo ln -s ../sites-available/myn6 001-myn6

You may want or need to adjust the contents of the newly created file
(``/etc/apache2/sites-available/myn6``) -- especially regarding the
following directives (see the comments accompanying them in the file):

* ``WSGIPassAuthorization``,
* ``WSGIDaemonProcess``,
* ``ErrorLog`` and ``LogLevel``,
* ``CustomLog``,
* ``ServerAdmin``.

.. seealso::

    You may want to read more about:

    * general Apache configuration:

      * http://httpd.apache.org/docs/2.2/configuring.html

    * ``modwsgi``-specific configuration:

      * https://modwsgi.readthedocs.io/en/stable/user-guides/configuration-guidelines.html
      * https://modwsgi.readthedocs.io/en/stable/configuration.html

If we have the default Apache configuration on Debian, we need to
disable the default site by removing the symbolic link:

.. code-block:: bash

    $ rm 000-default

Finally, let us restart the Apache daemon.  On Debian GNU/Linux it can
be done by executing:

.. code-block:: bash

    $ sudo service apache2 restart

Our application should be being served now.  Try visiting the
following URL (with any web browser or, for example, with the ``wget``
command-line tool):

``http://<your apache server address>/myn6/incidents.json``

(Of course, ``<your apache server address>`` needs to be replaced with
the actual host address of your Apache server, for example
``127.0.0.1`` or ``localhost``.)

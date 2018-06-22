0.6.2 (2016-05-11)
==================

Bugfixes:

* The ``n6sdk_api_test`` script now performs a cleanup after using the
  *pkg_resources* stuff (when executed with the ``--generate-config``
  option).

* A minor template fix in the *n6sdk* Pyramid scaffold.


Documentation-related changes:

* A lot of documentation fixes and improvements.


0.6.1 (2015-10-21)
==================

Documentation-related changes:

* The *0.6.0* release made the contents of the
  ``examples/BasicExample`` directory out-of-date.  Now, the directory
  has been completely removed and relevant documentation parts have
  been adjusted.

  Note: to generate an *n6sdk*-based project template (richly
  commented) you can use the ``pcreate -s n6sdk YourProjectName``
  command (within the virtualenv in which *n6sdk* has been installed).
  See also: the *Tutorial*.

* Several documentation fixes and improvements (including fixes and
  rearrangements in these *release notes*).


0.6.0 (2015-10-13)
==================

Significant or backward incompatible changes:

* Documentation: some **security-related** fixes in the *Installation
  for production...* and *Gluing it together* sections of the
  *Tutorial* -- especially, related to necessary access restrictions
  on ``production.ini`` file.

* A new utility script added: ``n6sdk_api_test`` -- a tool to perform
  basic validation of your *n6sdk*-based API.  (The script is
  automatically installed in the appropriate place when you install
  *n6sdk*.)

  See: the *n6sdk_api_test: API testing tool* chapter of the
  documentation.

* A new Pyramid *scaffold* added that makes it easy to create a
  skeleton of a new *n6sdk*-based REST API project -- just run the
  shell command: ``pcreate -s n6sdk YourProjectName`` (within the
  *virtualenv* in which *n6sdk* has been installed).

  See: the updated *Tutorial*.

* The `n6sdk.data_spec.DataSpec` data specification class has been
  deeply changed as well as a new data specification class has been
  added: `n6sdk.data_spec.AllSearchableDataSpec` (being a subclass of
  `DataSpec`).

  Now, all field specifications defined within `DataSpec` have the
  flag ``in_params`` set to ``None``, that is, are *not* marked as
  query parameters.

  It means that you need to create a subclass of `DataSpec` and, in
  that subclass, extend desired field specifications to *enable* them
  explicitly as query parameters (e.g., by using
  ``Ext(in_params='optional')``).

  Alternatively, you can create a subclass of `AllSearchableDataSpec`
  (which is a `DataSpec` subclass similar to the previous version of
  `DataSpec`, i.e., with most of fields marked as possible query
  parameters, using ``in_params='optional'``) -- then you may want to
  extend some field specifications (by using ``Ext(in_params=None)``)
  to *disable* them as query parameters.

  See: the updated *Tutorial*.

* Now, the field specification `DataSpec.url_pattern` requires that
  ``url_pattern`` values (concerning query parameter values as well as
  result values), if present, are *not* empty.

  To implement this restriction, a new boolean flag has been added to
  `n6sdk.data_spec.fields.UnicodeField` (and all its subclasses):
  ``disallow_empty``, settable as a constructor argument or a subclass
  attribute.  If the flag is true, values are not allowed to be empty.
  The default value of the flag is ``False``.

* A fix that affects `n6sdk.data_spec.DataSpec.fqdn`,
  `n6sdk.data_spec.fields.DomainNameField` as well as
  `n6sdk.regexes.DOMAIN_ASCII_LOWERCASE_REGEX` and
  `n6sdk.regexes.DOMAIN_ASCII_LOWERCASE_STRICT_REGEX`: now, the
  top-level part of a domain name (TLD) is no longer allowed to
  consist of digits only (thanks to that, the possibility to
  erroneously accept an IPv4 address as a domain name has been
  suppressed).

* A new incident category added to `DataSpec.category.enum_values`:
  ``'malware-action'``.

* A new field specification added to `DataSpec`: ``action``, intended
  to be used for incidents whose category is ``'malware-action'``
  (mentioned above).

* Exception handling has been revamped.  Among others, now
  ``content-type`` of HTTP error pages is set to ``text/plain`` (not
  to ``text/html``).

  A few significant changes related to that novelties have been
  applied to the following `n6sdk.pyramid_commons` classes:
  `DefaultStreamViewBase`, `HttpResource` and `ConfigHelper` (please
  analyze their code if you need detailed information); most notably:

  * the `DefaultStreamViewBase.concrete_view_class()` class method
    takes the fifth obligatory argument (and obligatory subclass
    attribute): ``adjust_exc`` (see the documentation of the method);

  * the `HttpResource.configure_views()` method (which calls
    `DefaultStreamViewBase.concrete_view_class()`) takes the second
    obligatory argument: ``adjust_exc``;

  * the `ConfigHelper.complete()` method (called, if needed, by
    `ConfigHelper.make_wsgi_app()`) registers appropriate Pyramid
    *exception views* as well as specifies appropriate callable as the
    ``adjust_exc`` argument for `HttpResource.configure_views()` (if
    you are interested in details, please, see the `ConfigHelper`
    source code, especially the code of `complete()` and of two new
    class methods: `exception_view()` and `exc_to_http_exc()`).

* Now, all `ConfigHelper` constructor arguments are *officially
  required* to be specified as keyword arguments (not as positional
  ones).

* The `pyramid` library (an existing external dependency) is now
  restricted to be not newer than version `1.5.7`.


Other changes:

* New external dependencies added: `python-cjson`_ and `requests`_
  (used by the ``n6sdk_api_test`` tool mentioned above).

* A bugfix: now, log messages from the `n6sdk.pyramid_commons` module
  are emitted using the ``'n6sdk.pyramid_commons'`` logger rather than
  the root logger.

* A new public helper function added:
  `n6sdk.pyramid_commons.renderers.data_dict_to_json()`; it defines
  how the standard renderers ``json`` and ``sjson`` serialize each
  data record (for details, see the documentation of the function);

* Various minor code cleanups, refactorizations and improvements.

* New and improved unit tests and doctests.

* A lot of documentation improvements and fixes.

.. _`python-cjson`: https://pypi.python.org/pypi/python-cjson
.. _`requests`: http://docs.python-requests.org/en/latest/


0.5.0 (2015-04-18)
==================

Significant or backward incompatible changes:

* Now, multiple values for a client query parameter can be specified
  in URL query strings in two alternative ways:

  * separated with commas, within one query string item (as in past
    *n6sdk* versions), e.g.: ``category=bots,dos-attacker,phish``;

  * as individual query string items (the way introduced in this
    *n6sdk* release), e.g.:
    ``category=bots&category=dos-attacker&category=phish``.

  Implementation of the extension caused the following changes in the
  *n6sdk* programming interfaces:

  * now, the argument for `<data specification>.clean_param_dict()` is
    a dictionary that maps query parameter names to *lists of
    individual uncleaned parameter values* (in past *n6sdk* versions
    it used to map query parameter names to *strings consisting of
    comma-separated uncleaned parameter values*);

  * extraction of individual query parameter values from the URL's
    query string -- including splitting comma-separated sequences of
    values -- is now *entirely outside* of the data specification
    machinery and field classes; the
    `n6sdk.data_spec.fields.Field._split_raw_param_value()` non-public
    method has been removed.

  * the interface of the `n6sdk.exceptions.ParamValueCleaningError`
    constructor has been extended a bit: now the second item of a
    3-tuple being an item of an `error_info_seq` argument can be
    either a single value (as previously) or a list of values.

  The *Tutorial* and other parts of the documentation have been
  adjusted appropriately.

* A lot of changes related to *data specification fields*:

  * New field classes in the `n6sdk.data_spec.fields` module:

    * `IPv6Field` (for IPv6 addresses),
    * `IPv6NetField` (for IPv6 network specifications),
    * `EmailSimplifiedField` (for e-mail addresses),
    * `IBANSimplifiedField` (for International Bank Account Numbers),
    * `ListOfDictsField` (for lists of dictionaries containing
      arbitrary data),
    * `DirField` (two-value enumeration: ``'src'`` or ``'dst'``),
    * `ExtendedAddressField` (for lists of address data items -- see
      the change in the ``address`` field specification, mentioned
      below).

  * Modified field classes in the `n6sdk.data_spec.fields`
    module:

    * `DictResultField`:

      * the ``key_to_subfield_factory`` attribute is
        no longer obligatory;
      * the ``required_keys`` attribute is gone;
      * the `clean_param_value()` method now raises `TypeError`
        instead of `NotImplementedError`;

    * `AddressField`:

      * now inherits from `ListOfDictsField`, not directly from
        `ResultListFieldMixin` and `DictResultField`;
      * the ``required_keys`` attribute is gone; ``ip`` subfield is still
        obligatory -- but now this requirement is implemented internally;
      * the `clean_param_value()` method now raises `TypeError`
        instead of `NotImplementedError`.

  * New field specifications added to the `n6sdk.data_spec.DataSpec`
    class:

    * ``time.until`` (`DateTimeField`, params-only),
    * ``active.until`` (`DateTimeField`, params-only),
    * ``modified`` (`DateTimeField`, results-only),
    * ``modified.min`` (`DateTimeField`, params-only),
    * ``modified.max`` (`DateTimeField`, params-only),
    * ``modified.until`` (`DateTimeField`, params-only),
    * ``ipv6`` (`IPv6Field`, params-only),
    * ``ipv6.net`` (`IPv6NetField`, params-only),
    * ``injects`` (`ListOfDictsField`, results-only),
    * ``registrar`` (`UnicodeLimitedField`),
    * ``url_pattern`` (`UnicodeLimitedField`),
    * ``username`` (`UnicodeLimitedField`),
    * ``x509fp_sha1`` (`SHA1Field`),
    * ``email`` (`EmailSimplifiedField`),
    * ``iban`` (`IBANSimplifiedField`),
    * ``phone`` (`UnicodeLimitedField`).

  * The ``address`` field specification (at
    `n6sdk.data_spec.DataSpec`) has been changed: now it is an
    `ExtendedAddressField` instance -- its subfields include:

    * ``ip``/``ipv6`` (`IPv4Field`/`IPv6Field`, obligatory -- which
      means that either ``'ip'`` or ```ipv6'``, but *not* both, must
      be present in each member dictionary),
    * ``cc`` (`CCField`),
    * ``asn`` (`ASNField`),
    * ``dir`` (`DirField`),
    * ``rdns`` (`DomainNameField`).

  * New categories added to `DataSpec.category.enum_values`:

    * ``'amplifier'``,
    * ``'backdoor'``,
    * ``'dns-query'``,
    * ``'flow'``,
    * ``'flow-anomaly'``,
    * ``'fraud'``,
    * ``'leak'``,
    * ``'vulnerable'``,
    * ``'webinject'``.

  The *Tutorial* has been adjusted appropriately.

* Both standard renderers (``json`` and ``sjson``) now add the ``"Z"``
  suffix (indicating the UTC time) to all *date+time* values.

* The ``sjson`` renderer now generates an additional empty line to
  indicate the end of data stream.


Other changes:

* A new external dependency: the `ipaddr`_ library.

* New and improved unit tests and doctests.

* Several documentation improvements and fixes.

.. _`ipaddr`: https://code.google.com/p/ipaddr-py/


0.4.0 (2014-12-23)
==================

This is the first public, *free*/*open-source*-licensed, release of
*n6sdk*.


Backward incompatible (though rather minor) changes:

* Changed behaviour of the standard ``json`` and ``sjson`` renderers
  (defined in `n6sdk.pyramid_commons.renderers` as the
  `StreamRenderer_json` and `StreamRenderer_sjson` classes): now they
  make use of a new helper function, `dict_with_nulls_removed()`, that
  replaces the old mechanism of recursive removing of
  ``None``-or-empty values from result dictionaries: previously,
  values equal to zero (such as ``0``, ``0.0`` or ``False``) were also
  removed; now they are kept (note that values being ``None``, empty
  containers and empty strings are still removed).

* Now, in the `n6sdk.pyramid_commons.DefaultStreamViewBase.call_api()`
  method, an `n6sdk.exceptions.TooMuchDataError` exception from
  `call_api_method()` or from data specification's
  `clean_result_dict()` causes `pyramid.httpexceptions.HTTPForbidden`
  and not `pyramid.httpexceptions.HTTPServerError`.

* The `n6sdk.class_helpers.singleton()` class decorator is now more
  lenient: instantiation does not count if `__init__()` of a decorated
  class raised (or propagated) an exception.


Other changes:

* Bugfix in the
  `n6sdk.pyramid_commons.DefaultStreamViewBase.concrete_view_class()`
  class method: now the check of the given renderer labels against the
  set of registered renderers works properly; previously it behaved
  nonsensically: accepted unregistered labels (causing further
  `KeyError` exceptions) and at the same time demanded that all
  registeted labels had to be used.

* Furthermore, `n6sdk.pyramid_commons.DefaultStreamViewBase` has a new
  class attribute: `break_on_result_cleaning_error`, by default set to
  ``True``.  In custom subclasses it can be set to ``False`` -- then
  result dictionaries that cannot be cleaned will be skipped (and a
  proper warning will be recorded to the logs) instead of causing
  `pyramid.httpexceptions.HTTPServerError`.

* The `n6sdk.pyramid_commons.renderers.dict_with_nulls_removed()`
  function (mentioned above) is exposed as a public helper (it may be
  useful when implementing custom renderers).

* The `n6sdk.data_spec.fields.Field` class (and its subclasses) as
  well as `n6sdk.datetime_helpers.FixedOffsetTimezone` -- have custom
  implementations of the `__repr__()` method (producing more readable
  results).

* Various minor code cleanups, refactorizations and improvements.

* New and improved unit tests and doctests.


Documentation-related news (including big ones!):

* Now the documentation is generated with `Sphinx`_.

* A new, long *Tutorial* has been added.

* A bunch of docstrings have been added.

* Contents of many docstrings have been improved.

* All docstrings are now *reStructuredText*-formatted and used as a
  part of the *Sphinx*-generated documentation.

* The former ``CHANGES.txt`` file has been
  *reStructuredText*-formatted, renamed to ``NEWS.rst`` and used as a
  part of the *Sphinx*-generated documentation.  There is also a new
  ``README.rst`` file, also included in the generated documentation.

* The former ``README.txt`` file has been moved to
  ``examples/BasicExample`` and sligthly improved.

* Furthermore, some other *BasicExample* improvements have been made
  (cleanups, refactorizations and minor fixes; among others, the
  `version` field in the *BasicExample*'s ``setup.py`` file no longer
  follows the *n6sdk* version; from now it is just ``"0.0.1"``).

.. _Sphinx: http://sphinx-doc.org/


0.3.0 (2014-08-12)
==================

Significant or backward incompatible changes:

* Network incident category ``"ddos"`` has been replaced with two
  separate categories: ``"dos-attacker"`` and ``"dos-victim"`` (see:
  `n6sdk.data_spec.CATEGORY_ENUMS`).

* `n6sdk.data_spec.fields.ResultListFieldMixin.clean_result_value()`
  no longer accepts `collections.Set` instances (now it accepts only
  `collection.Sequence` instances that are not `str`/`unicode`
  instances).


0.2.0 (2014-08-08)
==================

Significant or backward incompatible changes:

* Changes in the base data specification class
  (`n6sdk.data_spec.DataSpec`) and/or in the classes defined in the
  `n6sdk.data_spec.fields` module:

  * the `source` field is now an instance of a new class:
    `n6sdk.data_spec.fields.SourceField` -- which implements more
    restricted validation of values; now each value not only needs to
    be at most 32-characters long, but also it must consist of two
    non-empty parts, separated with exactly one dot character
    (``'.'``), containing only lowercase ASCII letters, digits and
    hyphens (``'-'``).

  * a change in `n6sdk.data_spec.fields.DateTimeField` that affects
    the `time`, `expires` and `until` fields of `DataSpec`: the
    `clean_result_value()` method now accepts also *ISO*-formatted
    date-and-time strings (not only `datetime.datetime` instances);

  * a change in `n6sdk.data_spec.fields.IntegerField` that affects the
    `sport`, `dport` and `count` fields of `DataSpec`: in
    `clean_result_value()`, the former strict *is-instance* check
    (`int`/`long`) has been replaced with a duck-typed coercion,
    accepting anything that can be converted using `int()` without
    information loss (e.g., a `float` being an integer number, such as
    ``42.0``, or a string being a decimal representation of an integer
    number, such as ``'42'`` -- but not ``'42.0'``);

  * a change in `n6sdk.data_spec.fields.ASNField` that affects the
    `address` (namely: `asn` of its subitems) and `asn` fields of
    `DataSpec`: the `clean_*_value()` methods now accept strings
    (`str`/`unicode`):

    * either being a decimal representation of an integer number in
      range ``0 .. 2**32-1``, e.g., ``'98765432'`` (formely only
      `clean_param_value()` accepted such strings),

    * or consisting of two dot-separated decimal representations of
      integer numbers in range ``0 .. 2**16-1``,
      e.g., ``'34567.65432'`` (formely such a notation was not accepted
      at all);

    note: ``clean_result_value()`` still accepts also `int` and `long`
    values in range ``0 .. 2**32-1`` (and still does not accept
    instances of `float` and other types).

  * a change in `n6sdk.data_spec.fields.CCField` that affects the
    `address` (namely: `cc` of its subitems) and `cc` fields of
    `DataSpec`: the `clean_*_value()` methods now accept also
    lowercase letters (which are automatically uppercased);

  * a change in `n6sdk.data_spec.fields.DomainNameSubstringField` that
    affects the `fqdn` (note: `DomainNameField` is a subclass of
    `DomainNameSubstringField`) and `fqdn.sub` fields of `DataSpec`:
    the value of `max_length` has been changed from ``253`` to
    ``255``;

  * a change in `n6sdk.data_spec.fields.DomainNameField` that affects
    the `fqdn` field of `DataSpec`: the regular expression the values
    are matched against is now more liberal (especially, underscores
    are now allowed; rationale: real-life domain names -- especially
    those maliciously constructed -- are not necessarily
    RFC-compliant; see: `n6sdk.regexes.DOMAIN_ASCII_LOWERCASE_REGEX`
    for details);

  * a change in `n6sdk.data_spec.fields.AnonymizedIPv4Field` that
    affects the `adip` field of `DataSpec`: the `clean_*_value()`
    methods now accept also ``'X'`` (uppercased ``'x'``) segments
    which are automatically lowercased;

  * the `adip` field is no longer enabled as a query parameter (field's
    `in_params` is now set to ``None``);

  * a change in `n6sdk.data_spec.fields.HexDigestField` that affects
    the `md5` and `sha1` fields of `DataSpec`: the `clean_*_value()`
    methods now accept also non-lowercase hexadecimal digit letters
    (which are automatically lowercased);

  * the former `hash_algo` attribute of `UnicodeField`
    class/subclasses/instances has been renamed to `hash_algo_descr`;

  * `n6sdk.data_spec.fields.URLField` is now a subclass of
    `n6sdk.data_spec.fields.URLSubstringField`;

  * `n6sdk.data_spec.fields.ListField` has been removed (use
    `ResultListFieldMixin` instead);

  * the former `n6sdk.data_spec.fields.AddressField` implementation
    has been replaced with a new one, especially the implementation of
    the methods has been factored out to new generic base classes:
    `ResultListFieldMixin` and `DictResultField`; some details have
    changed in a backwards-incompatible way -- notably:
    `key_to_subfield_class` has been renamed to
    `key_to_subfield_factory`.

* Changes in signatures of the `n6sdk.data_spec.BaseDataSpec` methods:
  `clean_param_dict()`, `clean_param_keys()`, `clean_result_dict()`,
  `clean_result_keys()`:

  * replaced the optional argument `keys_to_ignore` with the
    `ignored_keys` keyword-only argument (still optional),

  * added other optional arguments: `forbidden_keys`,
    `extra_required_keys`, `discarded_keys`.

* Changes in `n6sdk.pyramid_commons`:

  * functions `init_pyramid_config()` and `complete_pyramid_config()`
    have been removed; use the new `ConfigHelper` class instead (for
    details -- see its documentation, its code and the examples in
    ``examples/BasicExample``...);

  * a new function added: `register_stream_renderer()` (see below);

  * the signature of the `StreamResponse` class constructor changed:
    `renderer` has been renamed to `renderer_name`; also, now the
    value of that argument can be any name registered with the new
    function `register_stream_renderer()` (see its documentation for
    details); ``'json'`` and ``'sjson'`` are registered
    out-of-the-box;

  * the `DefaultStreamViewBase` class has been revamped in a
    backward-incompatibile way (please analyze its code if you need
    detailed information); most notably:

    * now the `concrete_view_class()` class method has completely
      different signature (see its documentation for details; note
      that `data_spec` now must be an instance, not a class); now each
      concrete subclass must have the `resource_id`, `renderers`,
      `data_spec` and `data_backend_api_method` attributes specified
      (for more information, also see the documentation of the
      `concrete_view_class()` class method mentioned above);

    * formely, the data specification's `clean_param_dict()` call
      performed in `prepare_params()` was guarded only against
      `ParamCleaningError` (transformed into
      `pyramid.httpexceptions.HTTPBadRequest`, when caught); now, also
      other exceptions are handled:
      `n6sdk.exceptions.AuthorizationError` (transformed into
      `pyramid.httpexceptions.HTTPForbidden`) and generic
      `n6sdk.exceptions.DataAPIError` (logged as an error and
      transformed into `pyramid.httpexceptions.HTTPServerError`) [note
      the symmetry between the `prepare_params()` and `call_api()`
      methods];

    * the possibility of specifying keyword arguments for data
      specification's `clean_*_dict()` calls as well as for data
      backend API's method call has been added (see the
      `get_clean_param_dict_kwargs()`,
      `get_clean_result_dict_kwargs()` and `get_extra_api_kwargs()`
      hook methods; the default implementation of each of them returns
      just an empty dict);

  * backward-incompatibile chages in the signature of the constructor
    of the `HttpResource` class:

    * now all arguments should be specified as keyword ones (never as
      positional ones, i.e., you cannot rely on argument order any
      more);

    * now `data_spec` must be an instance, not a class;

    note: see the documentation of this class for details.

* The module `n6sdk.data_backend_api` (together with the decorator
  `n6sdk.data_backend_api.data_backend_api_method`) has been removed.
  It is no longer required to decorate or mark your custom data
  backend API class or its methods in any special way.

* Unused `n6sdk.exceptions.InvalidCallError` has been removed.

* `n6sdk.exceptions.FieldValueTooLongError` has been added (see
  below).


Other changes:

* Appropriate adjustments in ``examples/BasicExample``.

* Some non-essential changes related to `n6sdk.data_spec.fields`:

  * if the given value is too long, the `clean_*_value()` methods of
    `n6sdk.data_spec.fields.UnicodeLimitedField` (and of its
    subclasses) now raise a new exception
    `n6sdk.exceptions.FieldValueTooLongError` (which is a subclass of
    `n6sdk.exceptions.FieldValueError` that was formely raised) -- see
    its documentation for details about attributes of its instances
    (that attributes can be useful, for example, when implementing
    external trimming of too long values...);

  * it is now explicitly required for
    `n6sdk.data_spec.fields.HexDigestField` instances (and for instances
    of its subclasses) that `num_of_characters` and `hash_algo_descr`
    are specified (as subclass attributes or constructor arguments);

  * it is now explicitly required for
    `n6sdk.data_spec.fields.UnicodeLimitedField` instances (and for
    instances of its subclasses) that `max_length` is not less than 1.

* Module `n6sdk.addr_helpers` added.

* Major refactorings and several minor additions, improvements, fixes
  and cleanups.

* Improvements in the documentation (a lot of improved/added
  docstrings, improved ``README.txt``, added ``CHANGES.txt``...) and
  code comments.

* ``MANIFEST.in`` and other package setup improvements and cleanups.

* New and improved unit tests and doctests.


0.0.1 (2014-04-25)
==================

Initial release.

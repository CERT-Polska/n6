# Changelog

*Note: some features of this document's layout were inspired by
[Keep a Changelog](https://keepachangelog.com/).*


## [4.4.0] - 2023-11-23

### Features and Notable Changes

#### Data Pipeline and External Communication

- [data sources, config] Added *parser* for the `shadowserver.msmq` source.

- [data sources, config] Removed support for the following data sources:
  `blueliv.map` and `darklist-de.bl` (removed both *collectors* and *parsers*!)
   as well as `shadowserver.modbus` (removed just this channel's *parser*).

- [data sources] The *parsers* for the `dataplane.*` sources have been
  changed to support the current data format (there was a need to change
  the delimiter and the row parsing mechanism...).

- [data sources] The *collector* for the `abuse-ch.ssl-blacklist` source
  (implemented in `n6datasources.collectors.abuse_ch` as the class named
  `AbuseChSslBlacklistCollector`) used to support the legacy state format
  related to the value of the `row_time_legacy_state_key` attribute -- it
  is no longer supported, as `_BaseAbuseChDownloadingTimeOrderedRowsCollect`
  (the local base class) no longer makes use of that attribute. *Note:*
  these changes are relevant and breaking *only* if you need to load a
  *collector state* in a very old format -- almost certainly you do *not*.

- [data sources] A new processing mechanism has been added to
  numerous existing *parsers* for `shadowserver.*` sources (by
  enhancing the `_BaseShadowserverParser` class, defined in the
  module `n6datasources.parsers.shadowserver`) -- concerning events
  categorized as `"amplifier"`. The mechanism is activated when a
  `CVE-...`-like-regex-based match is found in the `tag` field of
  the input data -- then the *parser*, apart from yielding an event
  (hereinafter referred to as a *basic* event) with `category` set to
  `"amplifier"`, also yields an *extra* event -- which is identical to the
  *basic* one, except that its `category` is set to `"vulnerable"` and its
  `name` is set to the regex-matched value (which is, basically, the CVE
  identifier). Because of that, `name` and `category` should no longer be
  declared as *parser*'s `constant_items`, so now `_BaseShadowserverParser`
  provides support for `additional_standard_items` (which is a *parser*
  class's attribute similar to `constant_items`). For relevant *parser*
  classes, the `name` and `category` items have been moved from their
  `constant_items` to their `additional_standard_items`.

- [data sources] Now the generic `*.misp` *collector* supports loading
  state also in its legacy Python-2-specific format.

- [data sources, data pipeline, lib] A new restriction (implemented in
  `n6lib.data_spec.fields`, concerning the `IPv4FieldForN6` and
  `AddressFieldForN6` classes) is that, from now on, the zero IP address
  (`0.0.0.0`) is *neither* a valid component IP within a *record dict's*
  `address` (i.e., its items' `ip`) or `enriched` (i.e., keys in the
  mapping being its second item), *nor* a valid value of a *record dict's*
  `dip`. Note that this restriction regards most of the *n6* pipeline
  components, especially data *parsers* (via the machinery of
  `n6lib.record_dict.RecordDict` *et consortes*...).

- [data pipeline] The name of the AMQP input queue declared by `n6enrich`
  has been changed (!) from `enrichement` to `enrichment`.

- [data pipeline] The `n6enrich` pipeline component (implemented in
  `n6datapipeline.enrich`): from now on, the zero IP address (`0.0.0.0`),
  irrespective of its exact formatting (i.e., regardless whether some
  octets are formatted with redundant leading zeros), is no longer taken
  into account when IPs are extracted from `url`s, and when `fqdn`s are
  resolved to IPs.

- [data pipeline, config] From now on, when `n6recorder`, during its
  activity (i.e., within `Recorder.input_callback()`...), encounters
  an exception which represents a *database/DB API error* (i.e., an
  instance of a `MySQLdb.MySQLError` subclass, possibly wrapped in
  (an) SQLAlchemy-specific exception(s)...) whose *error code* (i.e.,
  `<exception>.args[0]` being an `int`, if any) indicates a *fatal
  condition* -- then a `SystemExit(<appropriate message>)` is raised, so
  that the AMQP input message is requeued and the `n6recorder` executable
  script exits with a non-zero status. The set of *error codes* which are
  considered *fatal* (i.e. which trigger this behavior) is configurable --
  by setting the `fatal_db_api_error_codes` configuration option in the
  `recorder` section; by default, that set includes only one value: `1021`
  (i.e., the `ERR_DISK_FULL` code -- see:
  https://mariadb.com/kb/en/mariadb-error-codes/).

- [Portal, REST API, Stream API, data pipeline, lib] A *security-related*
  behavioral fix has been applied to the *event access rights* and *event
  ownership* machinery (implemented in `n6lib.auth_api`...): from now on,
  *IP-network-based access or ownership criteria* (those stored in the
  `criteria_ip_network` and `inside_filter_ip_network` tables of Auth DB)
  referring to networks that contain the zero IP address (`0.0.0.0`) are
  translated to IP address ranges whose lower bound is `0.0.0.1` (in other
  words, `0.0.0.0` is excluded). Thanks to that, *events without `ip` are
  no longer erroneously considered as matching* such IP-network-based
  criteria. In practice, *from the security point of view*, the fix is
  most important when it comes to REST API and Portal; for other involved
  components, i.e., `n6lilter` and `n6anonymizer`/Stream API, the security
  risk was rather small or non-existent. *Note:* as the fix is related to
  `n6filter`, it regards *also* values of `min_ip` in the `inside_criteria`
  part of the JSON returned by the Portal API's endpoint `/info/config`;
  they are displayed by the Portal's GUI in the *Account information*
  view, below the *IP network filter* label -- as IP ranges' lower
  bounds.

- [Portal, REST API, lib] A behavioral fix related to the one described
  above (yet, this time, not related to security) has been applied to the
  procedure of translation of *the `ip.net` request parameter* to the
  corresponding fragment of Event DB queries (see: the `ip_net_query()`
  method of `n6lib.db_events.n6NormalizedData`...): from now on, each
  value that refers to a network which contains the zero IP address
  (`0.0.0.0`) is translated to an IP address range whose lower bound is
  `0.0.0.1` (in other words, `0.0.0.0` is excluded); thanks to that,
  *events with no `ip`* are no longer erroneously included in such cases.

- [Portal, REST API, lib] A new restriction (implemented in
  `n6lib.data_spec.fields`, concerning the `IPv4FieldForN6` and
  `AddressFieldForN6` classes) is that the zero IP address (`0.0.0.0`) is
  no longer a valid value of the `ip` and `dip` request parameters
  received by REST API's endpoints and analogous Portal API's endpoints.
  Also, regarding the Portal's GUI, the front-end validation part related
  to the *IP* search parameter has been appropriately adjusted.

- [Portal, REST API, lib] The mechanism of result data cleaning
  (implemented as a part of a certain non-public stuff invoked in
  `n6lib.data_spec.N6DataSpec.clean_result_dict()`) has been enhanced in
  such a way that the `address` field of *cleaned result dicts* no longer
  includes any items with `ip` equal to the zero IP address (`0.0.0.0`),
  i.e., they are filtered out even if they appear in some Event DB records
  (they could when it comes to legacy data). Note that it is complemented
  by the already existing mechanism of removing from *raw result dicts*
  any `ip` and `dip` fields whose values are equal to the zero IP address
  (see: `n6lib.db_events.make_raw_result_dict()`...).

#### Setup, Configuration and CLI

- [data sources, data pipeline, config, docker/etc] Added, fixed, changed
  and removed several config prototype (`*.conf`) files in the directories:
  `N6DataSources/n6datasources/data/conf/`,
  `N6DataPipeline/n6datapipeline/data/conf/` and
  `etc/n6/`. *Note:* for some of them, manual adjustments in user's actual
  configuration files are required (see the relevant comments in those
  files...).

- [setup, lib] `N6Lib`'s dependencies: changed the version of `dnspython`
  from `1.16` to `2.4`. Also, added a new dependency, `importlib_resources`,
  with version locked as `>=5.12, <5.13`.

- [setup, data pipeline] `N6DataPipeline`'s dependencies: temporarily
  locked the version of `intelmq` as `<3.2`.

#### Developers-Relevant-Only Matters

- [data pipeline] `n6datapipeline.enrich.Enricher`: renamed the
  `url_to_fqdn_or_ip()` method to `url_to_hostname()`, and changed its
  interface regarding its return values: now the method always returns
  either a non-empty `str` or `None`.

- [lib] `n6lib.common_helpers` and `n6sdk.encoding_helpers`: renamed the
  `try_to_normalize_surrogate_pairs_to_proper_codepoints()` function to
  `replace_surrogate_pairs_with_proper_codepoints()`.

- [lib] Removed three functions from `n6lib.common_helpers`:
  `is_ipv4()`, `is_pure_ascii()` and `lower_if_pure_ascii()`.
  
- [lib] `n6lib.db_events`: removed `IPAddress`'s constant attributes
  `NONE` and `NONE_STR` (instead of them use the `n6lib.const`'s constants
  `LACK_OF_IPv4_PLACEHOLDER_AS_INT` and `LACK_OF_IPv4_PLACEHOLDER_AS_STR`).

- [lib] `n6lib.record_dict`: removed `RecordDict`'s constant attribute
  `setitem_key_to_target_key` (together with some internal *experimental*
  mechanism based on it...).

- [lib] `n6lib.generate_test_events`: several changes and enhancements
  regarding the `RandomEvent` class have been made, including some
  modifications regarding its *configuration specification*... Also, the
  configuration-related stuff has been factored out to a new mixin class,
  `RandomEventGeneratorConfigMixin`.

- [lib] `n6lib.url_helpers`: changed `normalize_url()`'s signature and
  behavior...

- [tests] `n6datasources.tests.parsers._parser_test_mixin.ParserTestMixin`
  (and inheriting *parser* test classes): added checking *raw format
  version tags* in parser tests (using the `ParserTestMixin`'s attribute
  `PARSER_RAW_FORMAT_VERSION_TAG`...).

### Less Notable Changes and Fixes

- [data sources] Added missing `re.ASCII` flag to regex definitions in a
  few parsers: `sblam.spam`, `spamhaus.drop` and `spamhaus.edrop` (note:
  before these fixes, the lack of that flag caused that the affected
  regexes were too broad...).

- [data sources, config] Restored, in the `ShadowserverMailCollector` section
  of the `N6DataSources/n6datasources/data/conf/60_shadowserver.conf` config
  prototype file, the (mistakenly deleted) `"Poland Netcore/Netis Router
  Vulnerability Scan":"netis"` item of the `subject_to_channel` mapping.

- [data pipeline] `n6enrich`: fixed a few bugs concerning extraction of
  a domain name (to become `fqdn`) or an IP address (to become `ip` in
  `address`...) from the hostname part of `url`. Those bugs caused that,
  for certain (rather uncommon) cases of malformed or untypical URLs,
  whole events were rejected, or (*only* for some cases and *only* if
  `__debug__` was false, i.e., when the Python's *assertion-removal
  optimization* mode was in effect) that the resultant event's `enriched`
  field erroneously included the `"fqdn"` marker whereas `fqdn` was *not*
  successfully extracted from `url`).

- [data pipeline] Fixed `n6anonymizer`: now the
  `_get_result_dicts_and_output_body()` method of
  `n6datapipeline.aux.anonymizer.Anonymizer` returns
  objects of the proper type (`bytes`).

- [Admin Panel] Fixed a *RIPE search*-related bug in Admin Panel (in
  `N6AdminPanel/n6adminpanel/static/lookup_api_handler.js` -- in the
  `RipePopupBase._getListsOfSeparatePersonOrOrgData()` function where the
  initial empty list was inadvertently added to the `resultList`, leading
  to duplicate data entries in certain cases; this update ensures that a
  new `currentList` is only added to `resultList` upon encountering a
  valid separator and contains data, preventing the addition of an empty
  initial list and the duplication of the first data set).

- [lib, Admin Panel] Added an `org`-key-based search feature to the
  `n6lib.ripe_api_client.RIPEApiClient`, enabling it to perform additional
  searches when encountering the `org` key. The enhancement allows for the
  retrieval and integration of organization-specific results into the
  existing data set, broadening the overall search capabilities (and,
  consequently, improving UX for users of Admin Panel, which makes use of
  `RIPEApiClient`).

- [lib] `n6lib.common_helpers`: from now on, the
  `ip_network_tuple_to_min_max_ip()` function (also available
  via `n6sdk.encoding_helpers`) accepts an optional flag argument,
  `force_min_ip_greater_than_zero`.

- [lib] `n6lib.common_helpers`: added the `as_str_with_minimum_esc()`
  function (also available via `n6sdk.encoding_helpers`).

- [lib] `n6lib.const`: added the
  `LACK_OF_IPv4_PLACEHOLDER_AS_INT` (equal to `0`) and
  `LACK_OF_IPv4_PLACEHOLDER_AS_STR` (equal to `"0.0.0.0"`) constants.

- [lib, tests] `n6lib.unit_test_helpers`: added to `TestCaseMixin` a new
  helper method, `raise_exc()`.

- [docker/etc] Replaced expired test/example certificates.

- [data sources, data pipeline, portal, setup, config, cli, lib, tests, docker/etc, docs]
  Various additions, fixes, changes, enhancements as well as some cleanups,
  and code modernization/refactoring...

- [lib] Various additions, changes and removals regarding *experimental* code.


## [4.0.1] - 2023-06-03

Fixed generation of the docs by upgrading `mkdocs` to the version `1.2.4`.


## [4.0.0] - 2023-06-03

**This release is a big milestone.**

Among others:

- the *n6 Portal* gained support for
  [OpenID Connect](https://openid.net/foundation/how-connect-works/)-based
  *single sign-on* ([SSO](https://en.wikipedia.org/wiki/Single_sign-on))
  authentication;

- the *n6 Stream API* ([STOMP](https://stomp.github.io/)-based) now
  supports authentication based on API keys (those which have already been
  accepted by the *n6 REST API*); the new mechanism, implemented as a part
  of the `N6BrokerAuthApi` package, replaces the previously used mechanism
  (which was based on X.509 client certificates);

- added a significant number of components obtaining and processing
  security event data from external sources: 26 *collectors* and 86
  *parsers*; now, in total, we have 35 *collectors* and 91 *parsers*
  (see the `N6DataSources` package);

- got rid of the Python-2-compatible legacy code (most of which were
  Python 2 versions of *collectors* and *parsers*) that used to reside in
  `N6Core`; the accompanying Python 2 packages (`N6CoreLib`, `N6Lib-py2`
  and `N6SDK-py2`) have also been removed; note that the components
  related to active data sources have been migrated to Python 3
  (8 *collectors* and 7 *parsers* -- now they reside in `N6DataSources`);
  therefore, *n6* is now Python-3-only (finally!);

- significant performance improvements have been accomplished: certain
  kinds of data queries (via the *n6 REST API* or *n6 Portal*) have become
  much faster, and `n6aggregator`'s memory consumption has been
  considerably reduced;

- also, many minor improvements, a bunch of fixes, some refactoring and
  various cleanups have been made.

Note that some of the changes are *not* backwards-compatible.


## [3.0.0] - 2021-12-01

**This release is a big milestone.** It includes, among others:

- migration to Python 3

- in the *n6* data pipeline infrastructure: optional integration
  with [IntelMQ](https://github.com/certtools/intelmq)

- in the *n6 Portal:* a new frontend (implemented using
  [React](https://reactjs.org/)), two-factor authentication
  (based on [TOTP](https://datatracker.ietf.org/doc/html/rfc6238)),
  user's/organization's own data management (including config update
  and password reset forms, with related e-mail notices), and other
  goodies...

- in the *n6 REST API:* API-key-based authentication

- and many, many more improvements, a bunch of fixes, as well as
  some refactoring, removals and cleanups...

Note that many of the changes are *not* backwards-compatible.

Also, note that most of the main elements of *n6* -- namely:
`N6DataPipeline`, `N6DataSources`, `N6Portal`, `N6RestApi`,
`N6AdminPanel`, `N6BrokerAuthApi`, `N6Lib` and `N6SDK` -- are now
Python-3-only (more precisely: are compatible with CPython 3.9).


## [Consecutive updates of 2.0 series...]

[...]


## [2.0.0] - 2018-06-22

**This is the first public release of *n6*.**


[4.4.0]: https://github.com/CERT-Polska/n6/compare/v4.0.1...v4.4.0
[4.0.1]: https://github.com/CERT-Polska/n6/compare/v4.0.0...v4.0.1
[4.0.0]: https://github.com/CERT-Polska/n6/compare/v3.0.0...v4.0.0
[3.0.0]: https://github.com/CERT-Polska/n6/compare/v2.0.6a2-dev1...v3.0.0
[Consecutive updates of 2.0 series...]: https://github.com/CERT-Polska/n6/compare/v2.0.0...v2.0.6a2-dev1
[2.0.0]: https://github.com/CERT-Polska/n6/tree/v2.0.0

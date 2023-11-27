# Changelog

The *[n6](https://n6.readthedocs.io/)* project uses a versioning scheme
***distinct from** Semantic Versioning*. Each *n6* version's identifier
consists of three integer numbers, separated with `.` (e.g.: `4.11.2`).
We can say it is in the `<FOREMOST>.<MAJOR>.<MINOR>` format -- where:

- `<MINOR>` is incremented on changes that are **backwards compatible**
  from the point of view of users, sysadmins and programmers. Note that
  such changes may still be backwards *incompatible* regarding any
  code or feature which is considered non-public or experimental (by
  convention or because it is explicitly marked as such) and for the
  demo/documentation/examples/experimentation-focused stuff in the
  `docker/`, `docs/` and `etc/` directories.

- `<MAJOR>` is incremented on more significant changes -- which typically
  are **backwards incompatible** from the point of view of users,
  sysadmins or programmers.

- `<FOREMOST>` is incremented very rarely, only for **big milestone**
  releases.

Some features of this document's layout were inspired by
[Keep a Changelog](https://keepachangelog.com/).


## [4.4.0] - 2023-11-23

### Features and Notable Changes

- [data sources, config] Added support for the `shadowserver.msmq` source
  (just by adding the *parser* for it, as there already exists one common
  *collector* for all `shadowserver.*` sources).

- [data sources, config] Removed support for the following sources:
  `blueliv.map` and `darklist-de.bl` (removed both *collectors* and
  *parsers*!) as well as `shadowserver.modbus` (removed just this source's
  *parser*).

- [data sources] The *parsers* for the `dataplane.*` sources have been
  changed to support the current data format (there was a need to change
  the delimiter and the row parsing mechanism...).

- [data sources] The *collector* for the `abuse-ch.ssl-blacklist` source
  (implemented in `n6datasources.collectors.abuse_ch` as the class named
  `AbuseChSslBlacklistCollector`) used to be able to load the *collector
  state* in a legacy format related to the value of the class attribute
  `row_time_legacy_state_key` -- that format is no longer supported, as
  the base class `_BaseAbuseChDownloadingTimeOrderedRowsCollect` no longer
  makes use of that attribute. *Note:* these changes are relevant and
  breaking *only* if you need to load your *collector state* in that old
  format -- almost certainly you do *not*.

- [data sources] A new processing mechanism has been added to
  numerous existing *parsers* for `shadowserver.*` sources (by
  enhancing the `_BaseShadowserverParser` class, defined in the
  `n6datasources.parsers.shadowserver` module) -- concerning events
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
  `dip`. Note that this restriction regards all *parsers* and most of the
  other data pipeline components (via the machinery of
  `n6lib.record_dict.RecordDict` *et consortes*...).

- [data pipeline] The name of the AMQP input queue declared by `n6enrich`
  has been changed (!) from `enrichement` to `enrichment`.

- [data pipeline] The `n6enrich` pipeline component (implemented in
  `n6datapipeline.enrich`): from now on, the zero IP address (`0.0.0.0`),
  irrespective of its exact formatting (i.e., regardless whether some
  octets are formatted with redundant leading zeros), is no longer taken
  into account when IPs are extracted from `url`s, and when `fqdn`s are
  resolved to IPs.

- [data pipeline, event db, config] From now on, when `n6recorder`, during
  its activity (i.e., within `Recorder.input_callback()`...), encounters
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

- [portal, rest api, stream api, data pipeline, lib] A *security-related*
  behavioral fix has been applied to the *event access rights and event
  ownership* machinery (implemented in `n6lib.auth_api`...): from now on,
  *IP-network-based access or ownership criteria* (those stored in the
  `criteria_ip_network` and `inside_filter_ip_network` tables of Auth DB)
  referring to networks that contain the zero IP address (`0.0.0.0`) are
  translated to IP address ranges whose lower bound is `0.0.0.1` (in other
  words, `0.0.0.0` is excluded). Thanks to that, *events without `ip` are
  no longer erroneously considered as matching* such IP-network-based
  criteria. In practice, *from the security point of view*, the fix is
  most important when it comes to Portal and REST API (considering that
  those components query Event DB, in whose records the absence of an IP
  is, for certain technical reasons, represented by the value `0` rather
  than `NULL`). For other involved components, i.e., `n6filter` and
  `n6anonymizer`/Stream API, the security risk was rather small or
  non-existent. *Note:* as the fix is also related to `n6filter`, it
  affects values of `min_ip` in the `inside_criteria` part of the JSON
  returned by the Portal API's endpoint `/info/config`; they are displayed
  by the Portal's GUI in the *Account information* view, below the *IP
  network filter* label -- as IP ranges' lower bounds.

- [portal, rest api, lib] A behavioral fix related to the one described
  above (yet, this time, not related to security) has been applied to the
  procedure of translation of *the `ip.net` request parameter* to the
  corresponding fragment of Event DB queries (see: the `ip_net_query()`
  method of `n6lib.db_events.n6NormalizedData`...): from now on, each
  value that refers to a network which contains the zero IP address
  (`0.0.0.0`) is translated to an IP address range whose lower bound is
  `0.0.0.1` (in other words, `0.0.0.0` is excluded); thanks to that,
  *events with no `ip`* are no longer erroneously included in such cases.

- [portal, rest api, lib] A new restriction (implemented in
  `n6lib.data_spec.fields`, concerning the `IPv4FieldForN6` and
  `AddressFieldForN6` classes) is that the zero IP address (`0.0.0.0`) is
  no longer a valid value of the `ip` and `dip` request parameters
  received by REST API's endpoints and analogous Portal API's endpoints.
  Also, regarding the Portal's GUI, the front-end validation part related
  to the *IP* search parameter has been appropriately adjusted.

- [portal, rest api, lib] The mechanism of result data cleaning
  (implemented as a part of a certain non-public stuff invoked in
  `n6lib.data_spec.N6DataSpec.clean_result_dict()`) has been enhanced in
  such a way that the `address` field of *cleaned result dicts* no longer
  includes any items with `ip` equal to the zero IP address (`0.0.0.0`),
  i.e., they are filtered out even if they appear in some Event DB records
  (they could when it comes to legacy data). Note that it is complemented
  by the already existing mechanism of removing from *raw result dicts*
  any `ip` and `dip` fields whose values are equal to the zero IP address
  (see: `n6lib.db_events.make_raw_result_dict()`...).

- [test rest api, config, lib] `n6lib.generate_test_events`: several
  changes and enhancements regarding the `RandomEvent` class have been
  made, including backward incompatible additions/removals/modifications
  of options defined by its *config spec*, affecting the way the optional
  *test REST API* application (provided by `n6web.main_test_api` *et
  consortes*...) is configured using `generator_rest_api.*` options...
  Also, most of the `RandomEvent`'s configuration-related stuff has been
  factored out to a new mixin class, `RandomEventGeneratorConfigMixin`.

#### System/Configuration/Programming-Only

- [data sources, data pipeline, config, docker/etc] Added, fixed, changed
  and removed several config prototype (`*.conf`) files in the
  directories: `N6DataSources/n6datasources/data/conf/`,
  `N6DataPipeline/n6datapipeline/data/conf/` and `etc/n6/`. *Note:* for
  some of them, manual adjustments in user's actual configuration files
  are required (see the relevant comments in those files...).

- [setup, lib] `N6Lib`'s dependencies: changed the version of `dnspython`
  from `1.16` to `2.4`. Also, added a new dependency, `importlib_resources`,
  with version locked as `>=5.12, <5.13`.

- [setup, data pipeline] `N6DataPipeline`'s dependencies: temporarily
  locked the version of `intelmq` as `<3.2`.

#### Programming-Only

- [data pipeline] `n6datapipeline.enrich.Enricher`: renamed the
  `url_to_fqdn_or_ip()` method to `url_to_hostname()`, and changed its
  interface regarding the return value: now it is always *either* a
  non-empty `str` *or* `None`.

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

- [lib] `n6lib.url_helpers`: changed `normalize_url()`'s signature and
  behavior...

- [tests] `n6datasources.tests.parsers._parser_test_mixin.ParserTestMixin`
  (and all inheriting *parser* test classes): added checking that if the
  *parser*'s `default_binding_key` includes the *raw format version tag*
  segment then that segment matches the test class's attribute
  `PARSER_RAW_FORMAT_VERSION_TAG`.

### Less Notable Changes and Fixes

- [data sources] Added missing `re.ASCII` flag to regex definitions in a
  few parsers: `sblam.spam`, `spamhaus.drop` and `spamhaus.edrop` (the
  lack of that flag caused that the affected regexes were too broad...).

- [data sources, config] Restored, in the `ShadowserverMailCollector` section
  of the `N6DataSources/n6datasources/data/conf/60_shadowserver.conf` config
  prototype file, the (mistakenly deleted) `"Poland Netcore/Netis Router
  Vulnerability Scan":"netis"` item of the `subject_to_channel` mapping.

- [data pipeline] `n6enrich`: fixed a few bugs concerning extraction of
  the hostname being a domain name (to become `fqdn`) or an IP address (to
  become `ip` in `address`...) from `url`. Those bugs caused that, for
  certain (rather uncommon) cases of malformed or untypical URLs, whole
  events were rejected, or (*only* for some cases and *only* if the
  Python's *assertion-removal optimization* mode was in effect) the
  resultant event's `enriched` field erroneously included the `"fqdn"`
  marker whereas `fqdn` was *not* successfully extracted from `url`.

- [data pipeline] Fixed `n6anonymizer`: now output bodies
  produced by the `_get_result_dicts_and_output_body()` method
  of `n6datapipeline.aux.anonymizer.Anonymizer` are of the proper
  type (`bytes`)...

- [admin panel] Fixed a *RIPE search*-related bug in the Admin Panel (in
  `N6AdminPanel/n6adminpanel/static/lookup_api_handler.js` -- in the
  `RipePopupBase._getListsOfSeparatePersonOrOrgData()` function where the
  initial empty list was inadvertently added to the `resultList`, leading
  to duplicate data entries in certain cases; this update ensures that a
  new `currentList` is only added to `resultList` upon encountering a
  valid separator and if it contains any data, preventing the addition of
  an empty initial list and the duplication of the first data set).

- [admin panel, lib] Extended the scope of data obtained from RIPE and
  displayed in the Admin Panel -- thanks to adding an `org`-key-based
  search feature to the `n6lib.ripe_api_client.RIPEApiClient`, which
  enables it to perform additional searches when encountering the `org`
  key; the enhancement allows for the retrieval and integration of
  *organization-specific* results into the existing data set (broadening
  the overall search capabilities).

- [docker/etc] Replaced expired test/example certificates.

- [data sources, data pipeline, portal, setup, config, cli, lib, tests,
  docker/etc, docs] Various additions, fixes, changes, enhancements as
  well as some cleanups and code modernization/refactoring.

#### Programming-Only

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

- [lib] Various additions, changes and removals regarding *experimental*
  code.


## [4.0.1] - 2023-06-03

- [docs, setup] Fixed generation of the docs by upgrading `mkdocs` to the
  version `1.2.4`.


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

Note that some of the changes are *not* backwards compatible.


## [Further updates of 3.0 series...]

[...]


## [3.0.1] - 2021-12-03

- [docs] A bunch of fixes and improvements regarding the documentation,
  including major changes to its structure, layout and styling.

- [setup] `do_setup.py`: regarding the default value of the option
  `--additional-packages` under Python 3, the version of the `mkdocs`
  package has been pinned (`1.2.3`), and the `mkdocs-material` package
  (providing the `material` docs theme) has been added (and its version is
  also pinned: `8.0.3`); regarding the same under Python 2, the `mkdocs`
  package has been removed.


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

Note that many of the changes are *not* backwards compatible.

Also, note that most of the main elements of *n6* -- namely:
`N6DataPipeline`, `N6DataSources`, `N6Portal`, `N6RestApi`,
`N6AdminPanel`, `N6BrokerAuthApi`, `N6Lib` and `N6SDK` -- are now
Python-3-only (more precisely: are compatible with CPython 3.9).


## [Updates of 2.0 series...]

[...]


## [2.0.0] - 2018-06-22

**This is the first public release of *n6*.**


[4.4.0]: https://github.com/CERT-Polska/n6/compare/v4.0.1...v4.4.0
[4.0.1]: https://github.com/CERT-Polska/n6/compare/v4.0.0...v4.0.1
[4.0.0]: https://github.com/CERT-Polska/n6/compare/v3.0.1...v4.0.0
[3.0.1]: https://github.com/CERT-Polska/n6/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/CERT-Polska/n6/compare/v2.0.6a2-dev1...v3.0.0
[Updates of 2.0 series...]: https://github.com/CERT-Polska/n6/compare/v2.0.0...v2.0.6a2-dev1
[2.0.0]: https://github.com/CERT-Polska/n6/tree/v2.0.0

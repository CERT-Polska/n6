# Changelog

The *[n6](https://n6.readthedocs.io/)* project uses a versioning scheme
_**distinct from** Semantic Versioning_. Each *n6* version's identifier
consists of three integer numbers, separated with `.` (e.g.: `4.12.1`).
We can say it is in the `<FOREMOST>.<MAJOR>.<MINOR>` format -- where:

- `<MINOR>` is incremented on changes that are **backwards compatible** from
  the point of view of users, sysadmins and backend programmers. Note that
  such changes may still be backwards *incompatible* regarding any code or
  feature which is considered non-public or experimental (by convention or
  because it is explicitly marked as such), any portions of the *n6 Portal*
  frontend's implementation (all JS/TS code and all HTML/CSS/etc.) as well
  as the documentation/experimentation/examples-focused stuff in the
  `docker/`, `docs/` and `etc/` directories.

- `<MAJOR>` is incremented on more significant changes -- which typically
  are **backwards incompatible** from the point of view of users, sysadmins
  or backend programmers.

- `<FOREMOST>` is incremented very rarely, only for **big milestone**
  releases.

Some features of this document's layout were inspired by
[Keep a Changelog](https://keepachangelog.com/).


## [4.22.0] (2025-04-05)

#### General Audience Stuff

- [setup, lib, etc/docker] **Dropped support for Python 3.9. From now on,
  only Python 3.11 is officially supported.** Debian 12 (*bookworm*) is
  (still) the recommended operating system, and CPython 3.11 is the
  recommended implementation of Python.

- [data sources] A new data source: `phishtank.verified` (collector and
  parser).

- [data pipeline] New components for e-mail notifications: `n6counter`,
  `n6notifier` and `n6notifier_templates_renderer` (implemented in the
  `n6datapipeline.notifier`, `n6datapipeline.counter` and
  `n6datapipeline.aux.notifier_templates_renderer` modules).

- [data pipeline, portal, rest api, lib] Modified `n6recorder` to fix a
  bug in *n6 REST API* (and the *n6 Portal*'s API), concerning only users
  of organizations with `full_access=True` in the Auth DB, which caused
  that resultant events' `client` lists might be incomplete (erroneously
  limited to the values of the `client` query parameter, or -- in results
  from `/report/inside` -- to the identifier of the querying user's
  organization). From now on, `n6recorder` additionally records copies of
  events' `client` lists in the `custom` column of the Event DB's `event`
  table; and both concerned web APIs, when generating their results, get
  `client` lists from it (rather than from the `client` column of the
  `client_to_event` table). *Warning regarding the transitional period:*
  for all older data, `client` lists are just *not included* in results!
  Modified the following `n6lib`'s submodules to implement the fix:
  `data_backend_api`, `db_events`, `record_dict`, `generate_test_events`;
  in particular, changed -- in a **backward incompatible** way -- the
  behavior and signature of the `n6lib.db_events.make_raw_result_dict()`
  function... A side benefit of those changes is an optimization: many
  database queries are now faster (*not only* for users of organizations
  with the `full_access=True` in the Auth DB).

- [portal, lib, config] Made significant changes/fixes/improvements
  related to the *n6 Portal*'s [OpenID
  Connect](https://openid.net/foundation/how-connect-works/)-based
  *single sign-on* authentication mechanism (implemented, in particular,
  in `n6lib.oidc_provider_api.OIDCProviderAPI`,
  `n6lib.pyramid_commons.OIDCUserAuthenticationPolicy` and
  `n6lib.pyramid_commons.N6LoginOIDCView`...).
  Now, when using an *identity provider*, it is possible to authenticate
  and automatically create new local user accounts (in Auth DB) --
  by matching tokens' `org_uuid` claim values against organizations'
  `org_uuid` stored in Auth DB. Also, among others, JSON Web Key Sets are
  now obtained in a more effective and reliable manner, and without the
  need to authenticate to the IdP server.
  **Added support for the following *n6 Portal*'s configuration options:**
  `oidc_provider_api.verify_audience` (default: `false`),
  `oidc_provider_api.required_audience` (default: empty, which means that
  the Portal API's URL will be used),
  `oidc_provider_api.idp_server_request_retries` (default: `3`),
  `oidc_provider_api.idp_server_request_backoff_factor` (default: `0.2`),
  `oidc_provider_api.idp_server_request_timeout` (default: `10`).
  **Removed support for the following *n6 Portal*'s configuration options:**
  `oidc_provider_api.client_id`,
  `oidc_provider_api.client_secret_key`,
  `oidc_provider_api.verify_ssl`.

- [admin panel, auth db, lib] New column in the Auth DB's `org` table (and
  new `n6lib.auth_db.models.Org`'s field): `org_uuid`. **What is important**
  from the point of view of the administrators of an *n6* instance is that
  the *Alembic migrations machinery* needs to be used to update the schema
  of the production Auth DB (for the instructions how to do it, see
  `N6Lib/n6lib/auth_db/alembic/README.md`).

- [portal] *Incidents* page: added, for users of organizations with
  `full_access=True`, the `client` data column (for all three data
  resources), together with a new filter (only for the `/report/threats`
  and `/search/events` resources).

- [portal] *Incidents* page: added a new dynamic behavior regarding which
  data columns are displayed and when; also, generally, much more columns
  are now available. Use the *Columns* drop-down list to lock the columns
  you want to keep displayed; click the *Reset Columns* button (a new one)
  to restore the dynamic behavior.

- [portal] Modified the formats of exported JSON and CSV files -- now they
  are more comprehensive (more columns...) and/or easier to process (JSON
  data format resembles that of the REST API's `*.json` resources...).

- [portal] Minor UX fixes/improvements.

- [docs] The *n6*'s [documentation](https://n6.readthedocs.io/):
  enhancements, updates and fixes. In particular, added the documentation
  describing installation of *n6 Stream API* (including the Docker-based
  variant).

#### System/Configuration/Programming-Only

- [config, etc/docker, portal, rest api, broker auth api, admin panel,
  data sources, data pipeline, lib] The `*.conf` configuration prototype
  files for `N6DataPipeline` and `N6DataSources` as well as for
  `N6AdminPanel` and `N6Lib` (*et consortes*...) are now stored
  solely in `etc/n6/` (we carefully merged the former contents of
  `N6DataPipeline/n6datapipeline/data/conf/` and
  `N6DataSources/n6datasources/data/conf/` into `etc/n6/`). In similar
  vein, moved the `*.ini` configuration prototype files for `N6RestApi`
  (*n6 Rest API*), `N6Portal` (the *n6 Portal*'s API) and
  `N6BrokerAuthApi` (our internal API related to the *n6 Stream API*'s
  RabbitMQ instance...) into `etc/web/conf/`. Also, updated, improved
  and/or renamed many of those files.

- [config, etc/docker, portal, rest api, broker auth api] Adjusted all
  concerned `*.ini` configuration prototype files, so that they no longer
  contain *inline* (i.e., `;`-only-prefixed appended to non-empty lines)
  comments, as such comments are unsupported if our *n6*-specific monkey
  patching of `configparser` is not applied early enough -- which may be
  the case when it comes to running *n6 REST API*, the *n6 Portal*'s API
  or the Broker Auth API (related to *n6 Stream API*...) without a
  `*.wsgi` file containing `import n6lib` as early as possible. Therefore,
  **using *inline* comments in any `*.ini` files is now deprecated!** (but
  it is still perfectly OK in `*.conf` files!)

- [lib, cli, tests] Changed some stuff related to tests and test
  helpers/tooling/configuration/discovery/execution, including some
  **backward incompatible** changes... In particular, loading `n6sdk`'s
  doctests using the standard `unittest`-specific mechanism is no longer
  supported (from now on, `n6sdk.tests.test_doctests.load_tests()` raises
  `RuntimeError`); use `pytest` instead (with the `--doctest-modules`
  option...). Also, added the `addopts = --import-mode=importlib -ra`
  option to the global configuration of `pytest` (in the top-level
  `pytest.ini` file).

- [cli, lib] Fixed
  `n6create_and_initialize_auth_db`/`n6lib.auth_db.scripts.CreateAndInitializeAuthDB`
  (and `_AuthDBConfiguratorForAlembicEnv`), so that the Auth DB config
  section name's base used by a `CreateAndInitializeAuthDB` instance (stored
  by it as `self.config_section`) is now used also by the Alembic machinery
  invoked by that instance (previously, the name's base used by the Alembic
  machinery was always `"auth_db"`, which was plain wrong if the name's base
  for that instance was customized to be something else).

- [cli, lib] Got rid of an annoying warning (`MYSQL_OPT_RECONNECT is
  deprecated and will be removed in a future version`), previously printed
  to *stderr* by `libmysqlclient`.

- [setup, lib] Removed the `python-keycloak` dependency of `N6Lib`.

- [portal, setup, tests] Regarding the implementation of the *n6 Portal*'s
  frontend (*React*-based TS/JS code and related resources, together with
  the development tooling...): made a bunch of additions/enhancements,
  improvements, fixes as well as upgrades/additions regarding external
  packages. Among others: significantly expanded and improved the test
  suite, in particular, added functional tests using `playwright`; did
  a lot of cleaning and refactoring; introduced `stylelint`...

- [etc/docker] Upgraded the MariaDB version to `10.11`. Replaced the Maria
  Docker image with an official one.

- [etc/docker, stream api, broker auth api] Added `docker-compose.yml` and
  `Dockerfile` files for the *n6 Stream API*'s broker and server...

- [lib, setup, config, etc/docker, tests, docs] Other additions, changes,
  improvements, fixes, cleanups and removals as well as some refactoring...

#### Programming-Only

- [lib] `n6sdk.data_spec.utils`: changed the
  `@cleaning_kwargs_as_params_with_data_spec` decorator -- so that, from now
  on, it ensures that any arguments to a function decorated with it that are
  to be bound to *positional-or-keyword* parameters are always treated as
  *keyword arguments* (so that they *are* validated with the decorator's
  *data-spec-based* machinery, regardless of whether they are given as
  *positional* or *keyword* arguments); plus, appropriately
  changed/adjusted the signatures of some public methods provided by
  `n6lib.auth_db.api.AuthManageAPI` -- given that, in particular, in the
  signature of a method to which the decorator is applied, from now on, the
  `self` parameter must be explicitly marked as *positional-only* (using the
  `/,` marker); the same is true for other parameters intended to be
  specified as positional arguments *and* to be excluded from the
  *data-spec-based* machinery's validation (see: `org` in the signature of
  `AuthManageAPI.create_new_user()`). *Note:* some of those changes are
  **backward incompatible**.

- [lib] `n6lib.jwt_helpers`: changed the signature of the `jwt_decode()`
  function by adding the `options` argument (optional...) -- as the 4th
  one, i.e., positionally *before* `required_claims`, though typically you
  will pass it and any further arguments as keyword (named) ones anyway...

- [lib] Added a new module: `n6sdk.func_helpers` -- containing the
  implementation of a new decorator: `@with_args_as_kwargs_if_possible` (see
  its docstring for more information...), needed to implement the changes to
  the decorator `@cleaning_kwargs_as_params_with_data_spec` described above.

- [lib] Added a module stub: `n6lib.func_helpers`; its `__all__` sequence
  includes the aforementioned `@with_args_as_kwargs_if_possible` decorator
  (imported from `n6sdk.func_helpers`) as well as a few helpers imported
  from `n6lib.common_helpers` (`@memoized`, `@deep_copying_result`,
  `@exiting_on_exception`, `with_flipped_args()`) -- intended to be moved
  into this module in the future...

- [lib] Added new tools in `n6lib.sqlalchemy_related_test_helpers`:
  `get_declared_db_structure()`, `get_reflected_db_structure()`,
  `fetch_db_content()`, `insert_db_content()`, `delete_db_content()`,
  `disabled_foreign_key_checks()` (plus a few auxiliary type aliases).

- [lib, admin panel] `n6adminpanel.app`: added a new mixin,
  `ListViewFormattingExtraFilesMixin`, which allows to inject Admin
  Panel's view with another CSS file that contains styles for *list*
  views' DOM objects.

- [lib, auth db] `n6lib.auth_db.fields`: added `UUID4SimpleField` for
  simplified validation of UUID values.


## [4.12.1] (2025-01-03)

#### General Audience Stuff

- [etc/docker, docs] Fixed/updated certain technical details in the base
  image's *Dockerfile*. Applied minor updates, fixes and improvements to
  various parts of the documentation (including this changelog).

#### System/Configuration/Programming-Only

- [setup, lib] Added the `redis==2.10.6` pinned requirement to
  `N6Lib/requirements`.


## [4.12.0] (2024-12-23)

#### General Audience Stuff

- [setup, lib, etc/docker] Debian 12 (*bookworm*) and CPython 3.11 are now
  the officially recommended operating system and Python implementation.
  (CPython 3.9 is still supported.)

- [data sources] New data sources: `turris-cz.greylist-csv` (collector and
  parser), `withaname.ddosia` (collector and parser) and `shadowserver.bgp`
  (just another `shadowerver` parser).

- [data sources] Changed the `shadowserver.ftp` parser's constant value of
  the `name` event attribute to `"ftp allow password wo ssl"` (previously
  it was `"ftp, clear text pass"`).

- [data sources] Fixed a bug in the `abuse-ch.urlhaus-urls` collector by
  removing the (mistakenly kept) rigid limit on numbers of events being
  sent.

- [data sources] Removed the `malwarepatrol.malurl` collector.

- [portal, rest api, stream api, admin panel, data pipeline] Added a new
  feature: *Ignore Lists*. From now on, *n6* administrators/operators can
  use Admin Panel to create and manage *Ignore Lists*, each identified by
  a unique *label*, with optional *comment*, flagged as *active* or not,
  and -- what is most interesting -- containing any number of *Ignored IP
  Networks* (*note:* bare IP addresses are also accepted; they are
  automatically converted to `.../32` networks). The `n6filter` component
  will mark as *ignored* (by setting the `ignored` event field to `True`)
  each event that contains the `address` field whose value is a
  *non-empty* list including *only* dicts with *ignored IP addresses* (by
  an *ignored IP address* we mean an `ip` item which matches at least one
  *Ignored IP Network* belonging to any active *Ignore List*); any other
  events are marked as *not ignored* (by setting the `ignored` field to
  `False`). For non-privileged users (i.e., those whose organizations have
  `full_access=False` in the Auth DB) results generated by Portal, REST
  API (+ Test REST API) and Stream API/`n6anonymizer` do *not* include
  events marked as *ignored*. On the other hand, for privileged users
  (those whose organizations have `full_access=True` in the Auth DB)
  results generated by those *n6* components include both *not ignored*
  and *ignored* events, and then each event contains the `ignored` field
  (set either to `True` or `False`) -- except that in the case of Stream
  API/`n6anonymizer` all users are treated as if they were non-privileged.
  Additionally, privileged users can filter results from REST API (and
  Portal API) by using a new query parameter: `ignored` (Boolean).

- [portal, admin panel, docs] Added a new feature: *Organization Agreements*.
  It allows the administrators/operators of an *n6* instance to use
  Admin Panel to define *optional* terms (agreements) which then can
  be accepted/rejected, via Portal, by any existing and new (future)
  users of *n6* -- on behalf of their organizations. The new feature is
  [comprehensively documented](https://n6.readthedocs.io/install_and_conf/opt/optional_agreements/).

- [portal, admin panel] Enhanced the *Edit organization settings* form in
  the Portal frontend and the corresponding backend stuff as well as the
  related Admin Panel stuff -- to allow adding *and/or* removing users
  within the logged user's organization (actually: requesting *n6*
  administrators/operators to, respectively, add/re-activate *and/or*
  deactivate users...).

- [portal, rest api, stream api, data sources, data pipeline, event db, lib] The
  **`name`** event field (event attribute) is now coerced by the *n6* data
  pipeline's machinery (namely, by `n6lib.record_dict.RecordDict`...) to
  **pure ASCII** (by replacing each non-ASCII character with `?`), and is,
  generally, required by all other parts of *n6* to be pure ASCII...
  (However, when it comes to how events' `id` values are computed by
  parsers, efforts have been made to keep that unaffected by the coercion
  -- so that resultant `id` values remain the same as previously for the
  same input values of `name`.) Events stored in the Event DB are now also
  expected to have `name` (if present) already coerced that way. (See also
  the descriptions of the Event-DB-related changes below...)

- [portal, rest api, data pipeline, event db, lib] The `count` event field
  (event attribute) is no longer constrained to be less than or equal to
  32767 (now its maximum value is 4294967295 which seems big enough for
  any practical purposes...). Therefore, `n6aggregator` does *not* set
  the `count_actual` field anymore. (See also the descriptions of the
  Event-DB-related changes below...)

- [portal, rest api, data pipeline, event db, lib] Non-BMP Unicode
  characters (i.e., Unicode codepoints greater than 0xFFFF) are now
  properly supported (if present) in values of the `url` and `target`
  event fields (attributes), i.e., now they can be reliably stored,
  looked up and retrieved in/from the Event DB, thanks to using the
  `utf8mb4` charset at the database level. (Previously, that was broken
  because of using the legacy max-3-bytes charset `utf8`. See also the
  descriptions of the Event-DB-related changes below...)

- [portal, rest api, event db, lib] Filtering the results by the `url`
  event field (attribute) -- by using the `url` or `url.sub` query
  parameter -- is now stricter in some ways, because the underlying
  MariaDB collation (for the Event DB's column `url` in the `event` table)
  changed from `utf8_unicode_ci` to `utf8mb4_bin` (in particular, now
  `url` values are compared in a *case-sensitive* manner).

- [portal, rest api, event db, lib] Filtering the results by the `target`
  event field (attribute) may behave in a slightly different way, because
  the underlying MariaDB collation (for the Event DB's column `target` in
  the `event` table) changed from `utf8_unicode_ci` to
  `utf8mb4_unicode_520_ci`.

- [portal, rest api, event db, lib] The `modified` event field (attribute)
  is now mandatory (i.e., guaranteed to be present in every event). See
  also the descriptions of the Event-DB-related changes below...

- [portal, rest api, data pipeline, auth db, lib] Implemented several
  performance enhancements/fixes and optimizations regarding retrieving
  and caching authorization data from the Auth DB (that is, concerning the
  stuff implemented in the `n6lib.auth_api` module and related modules;
  the addition of the `recent_write_op_commit` Auth DB table, mentioned
  later, is also related to that...). One of those enhancements is a new
  optional mechanism called *pickle cache* (see the related configuration
  options mentioned later...).

- [portal, rest api, lib] `n6lib.db_events.n6NormalizedData.like_query()`:
  fixed a bug causing injecting LIKE's wildcards when querying REST API or
  Portal API using query parameters `url.sub`/`fqdn.sub` (*SQL pattern
  injection*). It was *not* a security problem, but it caused that for
  some queries involving the affected parameters too large results
  (supersets of correct results) were obtained.

- [portal, lib] `n6lib.pyramid_commons.mfa_helpers`: fixed the value and
  the use of `MFA_CODE_MAX_VALIDITY_DURATION_IN_SECONDS` (previously named
  `MFA_CODE_MAX_ACCEPTABLE_AGE_IN_SECONDS`). Before the fix, if a Portal
  user successfully used an MFA code to log in, doing that "too early" but
  still within that MFA code's validity period (making use of the *clock
  drift tolerance* feature), it was then possible, for the same user, to
  successfully use the same MFA code once again, by doing that
  *sufficiently late yet still within the same validity period*. The crux
  of the bug was that the period of treating MFA codes as "already spent"
  was too short. (Note that the fixed bug does not look like a serious
  security flaw.)

- [portal] Applied many GUI/UX-related Portal fixes and enhancements...
  Among others, from now on, dates/times on the *Incidents* page are
  consistently processed/presented using *UTC* times; also, support for
  some additional search parameters have been added.

- [stream api, auth db, lib] Since now, all new organizations have Stream
  API enabled by default (the default value of the `stream_api_enabled`
  field of the `n6lib.auth_db.models.Org` model is now `True`).

- [admin panel, lib] All editable fields in the Admin Panel accepting an
  *IP network* (in the CIDR notation) now also accept a bare *IP address*
  (which is automatically converted to a `.../32` network). What has
  actually been changed is the validation procedure for all `ip_network`
  fields defined in `n6lib.auth_db.models...`. (To make that possible,
  `n6sdk.data_spec.fields.IPv4NetField`, and all its subclasses, gained a
  new option: `accept_bare_ip` -- of type `bool`, specifiable as a
  *subclass attribute* or a *keyword argument to the constructor*, with
  `False` as the default value).

- [admin panel, lib] Added a new column, *Is Active*, to the Admin Panel's
  *User* list view; the new column represents a newly added property of
  `n6lib.auth_db.models.User`: `is_active` -- whose value is always a
  logical negation of the (already existing) `User` model's field
  `is_blocked` (representing the `user` Auth DB table's column
  `is_blocked`).

- [docs] The *n6*'s [documentation](https://n6.readthedocs.io/): added a
  new article: *n6 REST API*; significantly improved/updated two existing
  articles: *n6 Stream API* and *Docker-Based Installation*; applied a bunch
  of fixes, improvements and updates to other parts of the documentation.

#### System/Configuration/Programming-Only

- [event db, lib] Made numerous changes to the schema and basic setup of
  the Event DB (see, in particular, the `etc/mysql/initdb/*.sql` files...).
  Namely: the MariaDB engine used for the Event DB is now [**RocksDB**](https://rocksdb.org/)
  (rather than *TokuDB*); the general Event DB's character set and
  collation (that apply, among others, to the `name` column in the `event`
  table...) are now `ascii` and `ascii_general_ci` (rather than the legacy
  max-3-bytes charset `utf8` with the collation `utf8_unicode_ci`), except
  that, in the `event` table, the character set and collation for the
  `url` column are now `utf8mb4` and `utf8mb4_bin`, and the character
  set and collation for the `target` column are now `utf8mb4` and
  `utf8mb4_unicode_520_ci`; the order of the components of the `event`
  table's primary key is now: `time`, `ip`, `id` (previously: `id`,
  `time`, `ip`); the `event` table's columns `modified` and `dip` are now
  `NOT NULL` (in the case of `dip`, the value 0 means that there is no
  actual value; note that, for that column, this convention has been
  used for a long time); the `event` table's columns `dport` and `sport`
  are now of type `SMALLINT UNSIGNED` (previously: `INTEGER`, which was an
  unnecessary waste of space); the `event` table's column `cc` is now of
  type `CHAR(2)` (previously: `VARCHAR(2)`); the `event` table's column
  `count` is now of type `INTEGER UNSIGNED` whose max. value is 4294967295
  (previously: `SMALLINT` with max. value 32767, which was far too small);
  several database indexes have been added/adjusted/removed; also, as a
  part of implementation of the aforementioned *Ignore Lists* feature,
  a new column has been added to the `event` table: `ignored`, of type
  `BOOL`; apart from all that, several SQL variables are now consistently
  set to sensible values (`max_allowed_packet`, `sql_mode`, `time_zone`)...
  **What is most important** from the point of view of the administrators
  of an *n6* instance is that a suitable migration of the whole production
  Event DB content needs to be performed (manually).

- [auth db, lib] As a part of implementation of the aforementioned
  *Ignore Lists* feature, added two new Auth DB tables: `ignore_list` and
  `ignored_ip_network`. Apart from them, added new Auth DB tables related
  to other features/mechanisms (also mentioned above...):
  `agreement`,
  `org_agreement_link`,
  `org_config_update_request_user_addition_or_activation_request`,
  `org_config_update_request_user_deactivation_request`,
  `recent_write_op_commit`,
  `registration_request_agreement_link`.
  Obviously, related model classes have been added as needed (see
  `n6lib.auth_db.models`) and any necessary field validators have been
  implemented (see `n6lib.auth_db.validators`). **What is important** from
  the point of view of the administrators of an *n6* instance is that the
  *Alembic migrations machinery* needs to be used to update the schema of
  the production Auth DB (for the instructions how to do it, see
  `N6Lib/n6lib/auth_db/alembic/README.md`).

- [config, data pipeline] From now on, the `n6recorder`'s
  **configuration option `connect_charset`** (in the configuration section
  `recorder`) is expected to be **set to the value `utf8mb4`** (*not* to
  the value `utf8` anymore!) -- unless there are some special
  circumstances and you really now what you are doing, and why!

- [config, portal, rest api] From now on, the **configuration
  option `sqlalchemy_event_db_connect_charset`** (in REST API's and Portal
  API's `*.ini` files) is expected to be **set to the value `utf8mb4`**
  (*not* to the value `utf8` anymore!) -- unless there are some special
  circumstances and you really now what you are doing, and why!

- [config, data sources] The collectors whose classes inherit (directly or
  indirectly) from `n6datasources.collectors.base.BaseDownloadingCollector`
  now support a new configuration option, `download_timeout`, which can be
  set to customize HTTP(s) request timeouts.

- [data pipeline] Added a new auxiliary executable: `n6exchange_updater`
  -- to update Stream-API-related AMQP exchange declarations and bindings
  (adding and deleting them as appropriate), according to the relevant
  Stream API settings in Auth DB. (The implementation of the component
  resides in the `n6datapipeline.aux.exchange_updater` module.)

- [config, portal, rest api] New configuration options regarding certain
  performance improvement mechanisms can now be specified in the REST API's
  and Portal API's `*.ini` files (see the `auth api prefetching configuration`
  part of the relevant configuration prototype files). In particular, the
  aforementioned optional mechanism called *pickle cache* can be activated
  (see the comments in the related configuration prototype files regarding
  the options `auth_api_prefetching.pickle_cache_dir` and
  `auth_api_prefetching.pickle_cache_signature_secret`; please, take
  seriously the security considerations those comments include...).

- [config, portal] A new configuration option, `session_cookie_sign_secret`,
  can now be specified in the Portal API's `*.ini` file to explicitly
  set the secret key for signing user session cookies (please, see the
  comments regarding that option in the related configuration prototype
  files...). By default, the option's value is empty, causing the legacy
  behavior (a new secret for signing session cookies being automatically
  generated on each start of the Portal API server application). *Note:*
  setting the option to a non-empty value is necessary if the Portal API
  server application is run using multiple OS processes (not just
  threads), otherwise user sessions cannot be handled properly.

- [config, portal, rest api, broker auth api, admin panel, data sources,
  data pipeline] From now on, wherever in *n6* an AMQP connection is
  established, authentication to RabbitMQ (the AMQP server) can be
  configured to be made using the PLAIN mechanism, i.e., with username
  and password (*note:* SSL-based EXTERNAL authentication, with an X.509
  client certificate, is still possible -- just no longer as the only
  option). To learn how to configure your *n6* components to use the PLAIN
  (username-and-password-based) mechanism, see respective comments in the
  relevant config prototype files: ad source/pipeline components --
  `00_global.conf`; ad input for collectors based on
  `n6datasources.collectors.AMQPCollector` -- `60_amqp.conf`; ad logging
  using `n6lib.log_helpers.AMQPHandler` -- either `logging.conf` or
  `production.ini` (the latter -- only regarding Portal API and REST API).
  Note that on production systems, no matter which authentication mechanism
  is in use (client-certificate-based or username-and-password-based),
  connections should *always* be secured with SSL (TLS).

- [config, portal, rest api, broker auth api, admin panel, data sources,
  data pipeline] From now on, in configuration files for any *n6*
  components, all configuration options that concern filesystem paths
  (or lists of filesystem paths) are expected to be specified using only
  **absolute paths**, i.e., relative paths might no longer be accepted.
  Note that paths like `~/something` and `~user/something` (intended to
  be expanded by replacing a `~`/`~user` marker with the user's home
  directory path) are still OK.

- [setup, lib, admin panel] Updated versions of some external dependencies
  (including some *security-related* cases...); also, added a few new
  dependencies.

- [lib, portal, rest api, broker auth api, admin panel, data sources,
  data pipeline, config, cli, docs, etc/docker, tests] Made a bunch of
  various changes/enhancements (**including backward incompatible** ones)
  and additions to the code (many related to the features and changes
  mentioned above...), plus various fixes/cleanups, some refactoring,
  modernization and adjustments/updates (among other things, many changes
  to accommodate some of the major Event-DB-related changes described
  above; as well as certain temporary hacks to ease the transition
  process)... Also, many tests (plus related data/fixtures/helpers) have
  been added, enhanced, fixed, refactored, adjusted/updated... More or
  less the same can be said about many *n6* components' configuration
  prototype files, and about some other configuration-or-Docker-related
  stuff...

- [portal, setup, tests] Regarding the implementation of the *n6 Portal*'s
  frontend (*React*-based TS/JS code and related resources, together with
  the development tooling...): a bunch of additions, changes/enhancements,
  fixes/cleanups as well as some refactoring, plus external package updates
  and additions... Among others, upgraded `Node`, `React` and `TypeScript`,
  and implemented a comprehensive `Jest`-based test suite...

- [etc/docker, docs] Added Mailhog to the Docker-related stuff.

#### Programming-Only

- [lib] Removed some
  constants/classes/methods/attributes/functions, in particular:
  `n6lib.data_backend_api.N6DataBackendAPI.EVENT_DB_LEGACY_CHARSET`,
  `n6lib.data_selection_tools.CondPredicateMaker.visit_RecItemParamCond()`
  (replaced with `visit_RecItemCond()` mentioned below),
  `n6lib.db_events.CustomInteger`,
  `n6lib.db_events.JSONText`,
  (replaced with `JSONMediumText` mentioned below),
  `n6lib.db_events.n6ClientToEvent.__json__()`,
  `n6lib.db_events.n6NormalizedData.to_raw_result_dict()`,
  `n6lib.ldap_api_replacement.LdapAPIConnectionError`,
  `n6lib.pyramid_commons.mfa_helpers.MFA_CODE_MAX_ACCEPTABLE_AGE_IN_SECONDS`
  (replaced with `MFA_CODE_MAX_VALIDITY_DURATION_IN_SECONDS` mentioned below).

- [lib] Added a new module: `n6lib.file_helpers` (providing
  three utility classes: `FileAccessor`, `StampedFileAccessor`,
  `SignedStampedFileAccessor`; and one utility function: `as_path()`;
  see their docstrings for more information...).

- [lib, data sources] Added numerous
  constants/classes/methods/attributes/functions, in particular:
  `n6datasources.base.parsers.BaseParser.ignored_csv_raw_row_prefixes`
  (and overridden, as appropriate, in some subclasses of `BaseParser`...),
  `n6lib.amqp_helpers.AMQPConnectionParamsError`,
  `n6lib.amqp_helpers.GUEST_PASSWORD`,
  `n6lib.amqp_helpers.GUEST_USERNAME`,
  `n6lib.amqp_helpers.MIN_REQUIRED_PASSWORD_LENGTH`,
  `n6lib.amqp_helpers.get_amqp_connection_params_dict_from_args.set_log_warning_func()`,
  `n6lib.amqp_helpers.SimpleAMQPExchangeTool`,
  `n6lib.auth_api.AuthAPI.get_ignore_lists_criteria_resolver()`,
  `n6lib.auth_db.fields.HTTPAbsoluteURLField`,
  `n6lib.auth_db.models.Agreement`,
  `n6lib.auth_db.models.IgnoredIPNetwork`,
  `n6lib.auth_db.models.IgnoreList`,
  `n6lib.auth_db.models.Org.agreements`,
  `n6lib.auth_db.models.org_agreement_link`,
  `n6lib.auth_db.models.OrgConfigUpdateRequest.user_addition_or_activation_requests`,
  `n6lib.auth_db.models.OrgConfigUpdateRequest.user_deactivation_requests`,
  `n6lib.auth_db.models.OrgConfigUpdateRequestUserAdditionOrActivationRequest`,
  `n6lib.auth_db.models.OrgConfigUpdateRequestUserDeactivationRequest`,
  `n6lib.auth_db.models.RecentWriteOpCommit`,
  `n6lib.auth_db.models.RegistrationRequest.agreements`,
  `n6lib.auth_db.models.registration_request_agreement_link`,
  `n6lib.auth_db.models.User.is_active`,
  `n6lib.class_helpers.LackOf`,
  `n6lib.common_helpers.ip_int_to_str()`
  (+ `n6sdk.addr_helpers.ip_int_to_str()`),
  `n6lib.common_helpers.PY_NON_ASCII_ESCAPED_WITH_BACKSLASHREPLACE_HANDLER_REGEX`
  (+ `n6sdk.regexes.PY_NON_ASCII_ESCAPED_WITH_BACKSLASHREPLACE_HANDLER_REGEX`),
  `n6lib.data_backend_api.N6DataBackendAPI.EVENT_DB_CONNECT_CHARSET_DEFAULT`,
  `n6lib.data_backend_api.N6DataBackendAPI.EVENT_DB_SQL_MODE`,
  `n6lib.data_selection_tools.IsTrueCond`,
  `n6lib.data_selection_tools.CondBuilder.RecItemCondBuilder.is_true()`,
  `n6lib.data_selection_tools.CondPredicateMaker.visit_RecItemCond()`,
  `n6lib.data_spec.N6DataSpec.ignored` (a new *event field* specification),
  `n6lib.db_events.JSONMediumText`,
  `n6lib.db_events.n6NormalizedData.single_flag_query()`,
  `n6lib.ldap_api_replacement.LdapAPI.peek_database_ver_and_timestamp()`,
  `n6lib.pyramid_commons.mfa_helpers.DELAY_TO_BE_SURE_THAT_MFA_CODE_EXPIRES`,
  `n6lib.pyramid_commons.mfa_helpers.MFA_CODE_MAX_VALIDITY_DURATION_IN_SECONDS`,
  `n6lib.record_dict.N6DataSpecWithOptionalModified`,
  `n6lib.record_dict.RecordDict.adjust_ignore()`,
  `n6lib.sqlalchemy_related_test_helpers.sqlalchemy_type_to_str()`,
  `n6lib.threaded_async.Future.peek_result()`,
  `n6lib.typing_helpers.HashObj`.


## [4.5.0] (2023-11-29)

#### General Audience Stuff

- [data pipeline, lib] `n6filter`: fixed a bug (in the machinery of
  `n6lib.auth_api.InsideCriteriaResolver`...) related to *event ownership
  criteria* (aka *"inside" resource events criteria*) regarding the very
  unlikely (yet not impossible) corner case of the `0.0.0.0/32` IP network
  defined as such a criterion in the Auth DB... The bug might make
  `n6filter` reject all incoming data (because of raised exceptions).

- [tests, docs] Non-major enhancements and fixes regarding some unit tests
  and documentation.

#### System/Configuration/Programming-Only

- [data sources, setup, config, etc/docker, tests] Globally renamed the
  `spamhaus.edrop` parser's class `SpamhausEdrop202303Parser` (defined in
  `n6datasources.parsers.spamhaus` and referred to in a few other places
  -- in particular, being the name of the-parser-dedicated configuration
  section!) to `SpamhausEdropParser`, as well as the executable script
  `n6parser_spamhausedrop202303` to `n6parser_spamhausedrop`; also, fixed
  `n6datasources.tests.parsers.test_spamhaus.TestSpamhausEdropParser` by
  removing its attribute `PARSER_RAW_FORMAT_VERSION_TAG`. The rationale
  for these changes is that no *raw format version tag* has ever been
  assigned to the `spamhaus.edrop` parser.

#### Programming-Only

- [tests] `n6datasources.tests.parsers._parser_test_mixin`: enhanced
  certain `ParserTestMixin`-provided checks related to *raw format
  version tags*.


## [4.4.0] (2023-11-23)

### Features and Notable Changes

#### General Audience Stuff

- [data sources, config] Added support for the `shadowserver.msmq` source
  (by adding the *parser* for it, as there already exists one common
  *collector* for all `shadowserver.*` sources; obviously, appropriate
  additions have been made in the *collector*'s and *parser*'s sections in
  the `N6DataSources/n6datasources/data/conf/60_shadowserver.conf` config
  prototype file).

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
  (i.e., the `ERR_DISK_FULL` code -- see [the error codes listing on the
  MariaDB website](https://mariadb.com/kb/en/mariadb-error-codes/)).

- [portal, rest api, stream api, data pipeline, lib] A *security-related*
  behavioral fix has been applied to the *event access rights and event
  ownership* machinery (implemented in `n6lib.auth_api`...): from now on,
  *IP-network-based access or ownership criteria* (those stored in the
  `criteria_ip_network` and `inside_filter_ip_network` Auth DB tables)
  referring to networks that contain the zero IP address (`0.0.0.0`) are
  translated to IP address ranges whose lower bound is `0.0.0.1` (in other
  words, `0.0.0.0` is excluded). Thanks to that, *events without `ip` are
  no longer erroneously considered as matching* such IP-network-based
  criteria. In practice, *from the security point of view*, the fix is
  most important when it comes to Portal and REST API (considering that
  those components query the Event DB, in records of which the absence of
  an IP is, for certain technical reasons, represented by the value `0`
  rather than `NULL`). For other involved components, i.e., `n6filter` and
  `n6anonymizer`/Stream API, the security risk was rather small or
  non-existent. *Note:* as the fix is also related to `n6filter`, it
  affects values of `min_ip` in the `inside_criteria` part of the JSON
  returned by the Portal API's endpoint `/info/config`; they are displayed
  by the Portal's GUI: in the *Account information* page, in the *"Inside"
  resource events criteria* section, below the *IP network filter* label
  -- as IP ranges' lower bounds.

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

- [rest api, config, lib] `n6lib.generate_test_events`: several changes
  and enhancements regarding the `RandomEvent` class have been made,
  including backward incompatible additions/removals/modifications of
  options defined by its *config spec*, affecting the way the optional
  *test REST API* application (provided by `n6web.main_test_api` *et
  consortes*...) is configured using `generator_rest_api.*` options...
  Also, most of the `RandomEvent`'s configuration-related stuff has been
  factored out to a new mixin class, `RandomEventGeneratorConfigMixin`.

#### System/Configuration/Programming-Only

- [data sources, data pipeline, config, etc/docker] Added, fixed, changed
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
  (and all inheriting *parser test* classes): added checking that if the
  *parser*'s `default_binding_key` includes the *raw format version tag*
  segment then that segment matches the test class's attribute
  `PARSER_RAW_FORMAT_VERSION_TAG`.

### Less Notable Changes and Fixes

#### General Audience Stuff

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
  events were rejected (because of an exception), or (*only* for some
  cases and *only* if the Python's *assertion-removal optimization* mode
  was in effect) the resultant event's `enriched` field erroneously
  included the `"fqdn"` marker whereas `fqdn` was *not* successfully
  extracted from `url`.

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

- [etc/docker] Replaced expired test/example certificates.

- [data sources, data pipeline, portal, setup, config, cli, lib, tests,
  etc/docker, docs] Various additions, fixes, changes, enhancements as
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


## [4.0.1] (2023-06-03)

- [docs, setup] Fixed generation of the docs by upgrading `mkdocs` to the
  version `1.2.4`.


## [4.0.0] (2023-06-03)

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


## Further updates of 3.0 series...

[...]


## [3.0.1] (2021-12-03)

- [docs] A bunch of fixes and improvements regarding the documentation,
  including major changes to its structure, layout and styling.

- [setup] `do_setup.py`: regarding the default value of the option
  `--additional-packages` under Python 3, the version of the `mkdocs`
  package has been pinned (`1.2.3`), and the `mkdocs-material` package
  (providing the `material` docs theme) has been added (and its version is
  also pinned: `8.0.3`); regarding the same under Python 2, the `mkdocs`
  package has been removed.


## [3.0.0] (2021-12-01)

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


## [2.0.0] (2018-06-22)

**The first public release of *n6*.**


[4.22.0]: https://github.com/CERT-Polska/n6/compare/v4.12.1...v4.22.0
[4.12.1]: https://github.com/CERT-Polska/n6/compare/v4.12.0...v4.12.1
[4.12.0]: https://github.com/CERT-Polska/n6/compare/v4.5.0...v4.12.0
[4.5.0]: https://github.com/CERT-Polska/n6/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/CERT-Polska/n6/compare/v4.0.1...v4.4.0
[4.0.1]: https://github.com/CERT-Polska/n6/compare/v4.0.0...v4.0.1
[4.0.0]: https://github.com/CERT-Polska/n6/compare/v3.0.1...v4.0.0
[3.0.1]: https://github.com/CERT-Polska/n6/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/CERT-Polska/n6/compare/v2.0.6a2-dev1...v3.0.0
[Updates of 2.0 series...]: https://github.com/CERT-Polska/n6/compare/v2.0.0...v2.0.6a2-dev1
[2.0.0]: https://github.com/CERT-Polska/n6/tree/v2.0.0

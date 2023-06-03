# Changelog

Starting with the 4.0.0 release, all notable changes to the
[code of _n6_](https://github.com/CERT-Polska/n6) are continuously
documented here.

Some features of this document's format are based on
[Keep a Changelog](https://keepachangelog.com/).


## [4.0.1] - 2023-06-03

Fixed generation of the docs by upgrading `mkdocs` to the version `1.2.4`.


## [4.0.0] - 2023-06-03

**This release is a big milestone.**

Among others:

- the *n6 Portal* gained support for OpenID-Connect-based *single
  sign-on* (SSO) authentication;

- the *n6 Stream API* (STOMP-based) now supports authentication based on
  API keys (the same ones that have already been accepted by the *n6 REST
  API*); the new mechanism replaces the previously used one (based on
  X.509 client certificates);

- added a bunch of new components which obtain and process security
  data from external sources: 26 *collectors* and 86 *parsers*; now,
  in total, we have in `N6DataSources` 35 *collectors* and 91 *parsers*;

- got rid of the legacy, *Python-2-only*, stuff (most of which were
  Python 2 versions *collectors* and *parsers*) that used to reside in
  `N6Core` and `N6CoreLib` (the *Python-2-only* variants of `N6Lib` and
  `N6SDK` have also been removed); note that the components related to
  active data sources has been migrated to Python 3 (8 *collectors* and
  7 *parsers* -- now they reside in `N6DataSources`); therefore, now *n6*
  is *Python-3-only* (finally!);

- significant optimizations have been accomplished: certain kinds of data
  queries (via the *n6 REST API* or *n6 Portal*) are much faster and
  `n6aggretator`'s memory consumption has been considerably reduced;

- also, many minor improvements, a bunch of fixes, some refactorization
  and various cleanups have been made...

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
  some refactorization, removals and cleanups...

Note that many of the changes are *not* backwards-compatible.

Also, note that most of the main elements of *n6* -- namely:
`N6DataPipeline`, `N6DataSources`, `N6Portal`, `N6RestApi`,
`N6AdminPanel`, `N6BrokerAuthApi`, `N6Lib` and `N6SDK` -- are now
*Python-3-only* (more precisely: are compatible with CPython 3.9).


[4.0.0]: https://github.com/CERT-Polska/n6/compare/v3.0.0...v4.0.0
[3.0.0]: https://github.com/CERT-Polska/n6/compare/v2.0.6a2-dev1...v3.0.0

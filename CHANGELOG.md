# Changelog

Starting with the 3.0.0 release, all notable changes applied to the
[code of _n6_](https://github.com/CERT-Polska/n6) are continuously
documented here.

The format of this file is based, to much extent, on
[Keep a Changelog](https://keepachangelog.com/).


## [3.0.0] - 2021-12-01

**This release is a big milestone.** It includes, among others:

* migration to Python 3
* in the *n6* data pipeline infrastructure: optional integration
  with [IntelMQ](https://github.com/certtools/intelmq)
* in the *n6 Portal:* a new frontend (implemented using
  [React](https://reactjs.org/)), two-factor authentication
  (based on [TOTP](https://datatracker.ietf.org/doc/html/rfc6238)),
  user's/organization's own data management (including config update
  and password reset forms, with related e-mail notices), and other
  goodies...
* in the *n6 REST API:* API-key-based authentication
* and many, many more improvements, a bunch of fixes, as well as
  some refactorization, removals and cleanups...

Beware that many of the changes are *not* backwards-compatible.

Note that most of the main elements of *n6* -- namely:
`N6DataPipeline`, `N6DataSources`, `N6Portal`, `N6RestApi`,
`N6AdminPanel`, `N6BrokerAuthApi`, `N6Lib` and `N6SDK` -- are now
*Python-3-only* (more precisely: are compatible with CPython 3.9).

The legacy, *Python-2-only* stuff -- most of which are *collectors* and
*parsers* (external-data-sources-related components) -- reside in
`N6Core` and `N6CoreLib`; the collectors and parsers placed in `N6Core`,
if related to non-obsolete external data sources, will be gradually
migrated to *Python-3-only* `N6DataSources` (so that, finally, we will
be able to rid of `N6Core` and `N6CoreLib`).  There are also
*Python-2-only* variants of `N6Lib` and `N6SDK`: `N6Lib-py2` and
`N6SDK-py2` (needed only as dependencies of `N6Core`/`N6CoreLib`).


[3.0.0]: https://github.com/CERT-Polska/n6/compare/v2.0.6a2-dev1...v3.0.0

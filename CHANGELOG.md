# Changelog

Starting with the 3.0.0 release, all notable changes to the
[code of _n6_](https://github.com/CERT-Polska/n6) are continuously
documented here.

The format of this document is based, to much extent, on
[Keep a Changelog](https://keepachangelog.com/).

## [3.12.0-beta1] - 2022-08-30

[TBD...]

## [3.0.1] - 2021-12-03

### Changes and Fixes

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
- in the _n6_ data pipeline infrastructure: optional integration
  with [IntelMQ](https://github.com/certtools/intelmq)
- in the _n6 Portal:_ a new frontend (implemented using
  [React](https://reactjs.org/)), two-factor authentication
  (based on [TOTP](https://datatracker.ietf.org/doc/html/rfc6238)),
  user's/organization's own data management (including config update
  and password reset forms, with related e-mail notices), and other
  goodies...
- in the _n6 REST API:_ API-key-based authentication
- and many, many more improvements, a bunch of fixes, as well as
  some refactorization, removals and cleanups...

Beware that many of the changes are _not_ backwards-compatible.

Note that most of the main elements of _n6_ -- namely:
`N6DataPipeline`, `N6DataSources`, `N6Portal`, `N6RestApi`,
`N6AdminPanel`, `N6BrokerAuthApi`, `N6Lib` and `N6SDK` -- are now
_Python-3-only_ (more precisely: are compatible with CPython 3.9).

The legacy, _Python-2-only_ stuff -- most of which are _collectors_ and
_parsers_ (external-data-sources-related components) -- reside in
`N6Core` and `N6CoreLib`; the collectors and parsers placed in `N6Core`,
if related to non-obsolete external data sources, will be gradually
migrated to _Python-3-only_ `N6DataSources` (so that, finally, we will
be able to rid of `N6Core` and `N6CoreLib`). There are also
_Python-2-only_ variants of `N6Lib` and `N6SDK`: `N6Lib-py2` and
`N6SDK-py2` (needed only as dependencies of `N6Core`/`N6CoreLib`).

[3.12.0-beta1]: https://github.com/CERT-Polska/n6/compare/v3.0.1...v3.12.0b1
[3.0.1]: https://github.com/CERT-Polska/n6/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/CERT-Polska/n6/compare/v2.0.6a2-dev1...v3.0.0

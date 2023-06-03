# Implementing a New Data Source

XXX NOT FINISHED!!!

!!! warning "TODO note"

    **This guide needs essential updates regarding the migration of *n6* from
    Python 2.7 to 3.9** (as well as other related and unrelated changes);
    especially that the *n6*'s data sources and data pipeline stuff now
    works under Python 3.9 and resides in `N6DataSources` and
    `N6DataPipeline` (where various interface details differ from the old,
    now removed, Python-2.7-only stuff which used to be kept in `N6Core`).

The aim of this guide is to describe how to implement new _n6_
components necessary for collecting and parsing data from some
external security data source.

**This guide consists of two parts:**

- [Collectors](collectors/index.md).
  The first part focuses on **_collectors_** which are _n6_'s data entry
  points. The job of a _collector_ is to obtain data from some external
  data source (for example, from a particular web site) and send those
  data for further processing.

- [Parsers](parsers/index.md).
  The other part focuses on **_parsers_** which are the next stage of
  the _n6_'s data processing pipeline. The job of a _parser_ is to
  parse and validate external data obtained by the corresponding
  collector, transform those data to a form digestible by _n6_ (i.e.,
  _normalize_ the data), and then send those (already _normalized_)
  data for further processing.

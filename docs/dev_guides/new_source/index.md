# Implementing a New Data Source

!!! warning "TODO note"

    **This guide needs an update regarding the recent migration of *n6* from
    Python 2.7 to 3.9**, especially that the *n6*'s data sources and data
    pipeline stuff now works under Python 3.9 and resides in `N6DataSources`
    and `N6DataPipeline` (where some names and other interface details
    differ from the corresponding, Python-2.7-only, legacy stuff kept in
    `N6Core`).


The aim of this guide is to describe how to implement new *n6*
components necessary for collecting and parsing data from some
external security data source.

**This guide consists of two parts:**

* [Collectors](collectors/index.md).
  The first part focuses on ***collectors*** which are *n6*'s data entry
  points.  The job of a *collector* is to obtain data from some external
  data source (for example, from a particular web site) and send those
  data for further processing.

* [Parsers](parsers/index.md).
  The other part focuses on ***parsers*** which are the next stage of
  the *n6*'s data processing pipeline.  The job of a *parser* is to
  parse and validate external data obtained by the corresponding
  collector, transform those data to a form digestible by *n6* (i.e.,
  *normalize* the data), and then send those (already *normalized*)
  data for further processing.

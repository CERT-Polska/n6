# Implementing a New Data Source (Developer Guide)

The aim of this guide is to describe how to implement new *n6*
components necessary for collecting and parsing data from some
external security data source.

**TBD: this part needs an update regarding the stuff that now works
under Python 3.9 and resides in `N6DataPipeline` and `N6DataSources`
(*not* in `N6Core` where only the legacy Python-2.7 stuff resides).**


## The guide's contents

This guide consists of two parts:

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

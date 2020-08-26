# Implementing a New Data Source (Developer Guide)

The aim of this guide is to describe how to implement *n6* components
that are necessary for collecting and parsing data from a new source.


## Overview

This guide consists of two main parts:

* The first one focuses on ***collectors*** which are the main *n6*'s
  data entry points.  With a *collector* we are able to obtain some
  external data (for example, from a particular web site) and send those
  data for further processing.

* The other one focuses on ***parsers*** which are the next stage of the
  *n6*'s external data processing pipeline: *parsers* come right after
  *collectors*. Their job is to transform obtained data to a form
  digestible by *n6*.


Contents
--------

* [Collectors](collectors/index.md)
* [Parsers](parsers/index.md)

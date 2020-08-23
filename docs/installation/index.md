# Step-by-Step Installation Guide

The goal of this guide is to give you an example of how you can glue the
relevant elements together in a (relatively) easy way, so that you can
learn -- by monitoring and experimenting with the stuff -- how the *n6*
system works and how you can interact with it.


## Important: what these materials *are* and what they are *not*

This installation guide, as well as the stuff you can find in the `etc/`
and `docker/` directories of the *n6* source code repository, concern
setting up an *n6* instance just for testing, exploration and
experimentation, that is, **not for production** (at least, *not*
without a careful security-focused adjustment).

In other words, these materials are *not* intended to be used as a
recipe for a secure production setup -- in particular, when it comes to
(but not limited to) such issues as X.509 certificates (note that those
in the `etc/ssl/` directory of the source code repository are purely
example ones), authentication and authorization settings (which in these
materials are, generally, either skipped or reduced to what is necessary
just to run the stuff), or file access permissions.

It should be obvious that an experienced system administrator and/or
security specialist should prepare and/or carefully review and adjust
any configuration/installation/deployment of services that are to be
made production ones, in particular if those services are to be made
public.


## Introduction

*n6* infrastructure depends on:

* a message broker - RabbtiMQ,
* SQL database - MariaDB with TokuDB engine,
* installed rabbitmq-server, mariadb with tokudb engine.

It is also highly recommended to have installed:

 * a No-SQL database - MongoDB,
 * a web server - Apache2.

This installation guide assumes that you use **Linux Debian 10 (Buster)**, with a
non-root `dataman` user account created (there is a section on how to create the _dataman_ user).

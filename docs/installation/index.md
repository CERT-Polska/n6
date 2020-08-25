# Step-by-Step Installation Guide: Introduction

The goal of this guide is to give you an example of how you can glue the
relevant elements together in a (relatively) easy way, so that you can
learn -- by setting up your own *n6* instance, running it, then
monitoring and experimenting with it -- how the *n6* system works and
how you can interact with it.

> **Note:** if you are in a hurry you may want to try the
> [Docker-Based Installation Guide](../docker) instead.


## Important: what these materials *are* and what they are *not*

This installation guide, as well as the stuff you can find in the
[`etc/`](https://github.com/CERT-Polska/n6/tree/master/etc) directory of
the *n6* source code repository, concern setting up an *n6* instance
just for testing, exploration and experimentation, i.e., **not for
production** (at least, *not* without careful security-focused
adjustments).

In other words, these materials are *not* intended to be used as a
recipe for a secure production setup -- in particular, when it comes to
(but not limited to) such issues as X.509 certificates (note that those
in the [`etc/ssl/*`](https://github.com/CERT-Polska/n6/tree/master/etc/ssl)
directories of the source code repository are purely example ones --
they should *never* be used for anything related to production
systems!), authentication and authorization settings (which in these
materials are, generally, either skipped or reduced to what is necessary
just to run the stuff), or file access permissions.

It should be obvious that an experienced system administrator and/or
security specialist should prepare and/or carefully review and adjust
any configuration/installation/deployment of services that are to be
made production ones, in particular if those services are to be made
public.


## Basic Requirements

The required operating system is a contemporary **GNU/Linux**
distribution.  This installation guide assumes that you use **Debian 10
(Buster)**, with a non-root `dataman` user account created (there is a
section on how to create that user).

Moreover, the *n6* infrastructure depends on:

* **RabbitMQ** (an AMQP message broker),
* **MariaDB** (a SQL database server) with the TokuDB engine.

To run some of the *n6* components it is also required to have installed:

* **MongoDB** (a NoSQL database server),
* **Apache2** (a web server).

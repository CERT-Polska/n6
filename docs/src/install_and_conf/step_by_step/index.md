# Step-by-Step Installation

The goal of this guide is to show you how to manually set up your own
instance of the *n6* system, so that you can learn -- by installing,
configuring, running and experimenting with the stuff -- what the basic
building blocks of *n6* are and how they interact with each other and
with the outside world.

!!! note

    If you are in a hurry, you may want to try the
    [Docker-Based Installation](../docker.md) guide instead.

!!! warning "Disclaimer: what these materials _are_ and what they are _not_"

    This installation guide, as well as the stuff you can find in the
    [`etc/`](https://github.com/CERT-Polska/n6/tree/master/etc) directory
    of the *n6* source code repository, concern setting up an *n6* instance
    just for testing, exploration and experimentation, i.e., **not for
    production** (at least, *not* without careful security-focused
    adjustments).

    In other words, these materials are *not* intended to be used as a
    recipe for a secure production setup -- in particular, when it comes to
    (but not limited to) such subjects as X.509 certificates (note that those
    in the [`etc/ssl/*`](https://github.com/CERT-Polska/n6/tree/master/etc/ssl)
    directories of the source code repository are purely example ones --
    they should *never* be used for anything related to production
    systems!), authentication and authorization settings (which in these
    materials are, generally, either skipped or reduced to what is necessary
    just to run the stuff), or file access permissions.

    It should be obvious that an experienced system administrator or
    security expert should prepare and/or carefully review and adjust
    any configuration/installation/deployment of services that are to be
    made production ones, in particular if those services are to be made
    public.

## This guide's contents

* [System Preparation](system.md)
* [Installing *n6* Components](installation.md)
* [Configuring *n6* Components](config.md)
* [Trying It Out](check.md)
* Delving Deeper:
    * [Managing *n6 Pipeline* Components with *Supervisor*](supervisor.md)
    * [*n6 Portal* -- Some Finer Points](portal_finer_points.md)

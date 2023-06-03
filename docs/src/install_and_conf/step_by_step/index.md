# Step-by-Step Installation

!!! warning "TODO note"

    **This guide needs essential updates regarding:**

    * **The migration of *n6* from Python 2.7 to 3.9** (as well as the
      related upgrades applied to other software in use, including the OS).
      Notably, the current implementation of the *n6* data pipeline resides in
      the top-level dir `N6DataPipeline` (Python-3-only), *not* in the removed
      top-level dir `N6Core` (where the legacy Python-2 stuff used to be kept).

    * **The swich to a brand new frontend of *n6 Portal*** (*React*-based).

## Opening remarks

The goal of this guide is to give you an example of how you can glue the
relevant elements together in a (relatively) easy way, so that you can
learn -- by setting up your own _n6_ instance, running it, then
monitoring and experimenting with it -- how the _n6_ system works and
how you can interact with it.

!!! note

    If you are in a hurry you may want to try the
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

## This guide's contents

- [System Preparation](system.md)
- [Installation of _n6_ Components](installation.md)
- [Configuration of _n6_ Pipeline](pipeline_config.md)
- [Certificates](certificates.md)
- [Configuration of _n6_ Web Components](web_components_config.md)
- [Supervisor](supervisor.md)

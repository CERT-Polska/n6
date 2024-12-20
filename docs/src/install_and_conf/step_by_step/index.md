# Step-by-Step Installation

## Opening remarks

The goal of this guide is to show you how to set up your own instance of *n6* and give you deeper understanding of *n6* system. 
You can also delve deeper into each of the component or even glue the
relevant elements together. So that you can learn -- by setting up your own *n6* instance, running it, then
monitoring and experimenting with it -- how the *n6* system works and
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
The quick installation path:

- [System Preparation](system.md)
- [Installation of *n6* Components](installation.md)
- [Pre-Setup Configuration](config.md)
- [Setting Up Instance of *n6*](setup.md)
- [Check n6 Data Flow & Web Services](check.md)

To delve deeper:

- [Configuration of *n6* Pipeline](pipeline_config.md)
- [Examination of *n6* Data Flow](examining_data_flow.md)
- [Certificates](certificates.md)
- [Configuration of *n6* Web Components](web_components_config.md)
- [Supervisor](supervisor.md)

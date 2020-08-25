# Important: what this stuff *is* and what it is *not*

The stuff you can find in the `etc/` and `docker/` directories of the
*n6* source code repository is meant to help you set up an *n6* instance
for testing, exploration and experimentation, i.e., **not for
production** (at least, *not* without careful security-focused
adjustments).

In other words, these materials are *not* intended to be used as a
recipe for a secure production setup -- in particular, when it comes to
(but not limited to) such issues as X.509 certificates (note that those
in the `etc/ssl/*` directories of the source code repository are purely
example ones -- they should *never* be used for anything related to
production systems!), authentication and authorization settings (which
in these materials are, generally, either skipped or reduced to what is
necessary just to run the stuff), or file access permissions.

It should be obvious that an experienced system administrator and/or
security specialist should prepare and/or carefully review and adjust
any configuration/installation/deployment of services that are to be
made production ones, in particular if those services are to be made
public.

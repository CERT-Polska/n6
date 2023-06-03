---
hide:
  - toc
---

# Architecture and Data Flow Overview

The _n6_'s overall architecture and data flow can be described schematically as follows:

![`[external data sources] → [n6collector_...]`; `[n6collector_...] -(AMQP)→ [n6archiveraw (aka archiver)] → [Archive DB (NoSQL)]`; `[n6collector_...] -(AMQP)→ [n6parser_...] -(AMQP)→ [n6aggregator (hi-freq data only)] -(AMQP)→ [n6erich (aka enricher)] -(AMQP)→ [n6comparator (blacklist data only)] -(AMQP)→ [n6filter] -(AMQP)→ [n6recorder] → [Normalized Event DB (SQL)]`; `[Normalized Event DB (SQL)] → [web: REST API, Portal API+GUI] -(HTTPS)→ [external clients]`; `[Auth DB (SQL)] → [n6filter]`; `[Auth DB (SQL)] → [web: REST API, Portal API+GUI]`; `[Auth DB (SQL)] ←→ [web: Admin Panel]`. Note: the `-(AMQP)→` arrows denote communication via an AMQP broker (RabbitMQ); other arrows denote direct communication (using various protocols); the `[n6...]` square brackets denote executable Python scripts; the `[web: ...]` square brackets denote HTTPS services (Apache2 + mod_wsgi + Python).](img/data_flow.png)

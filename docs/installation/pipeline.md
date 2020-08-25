# Data Flow Overview

*n6*'s data flow can be described schematically as follows:

![`[external data sources...] → [n6collector_*]`; `[n6collector_*] -(AMQP)→ [n6archiveraw (aka archiver)] → [Archive DB (NoSQL)]`; `[n6collector_*] -(AMQP)→ [n6parser_*] -(AMQP)→ [n6aggregator (hi-freq data only)] -(AMQP)→ [n6erich (aka enricher)] -(AMQP)→ [n6comparator (bl data only)] -(AMQP)→ [n6filter] -(AMQP)→ [n6recorder] → [Normalized Event DB (SQL)]`; `[Normalized Event DB (SQL)] → [REST API, Portal API+GUI] -(HTTPS)→ [external clients...]`; `[Auth DB (SQL)] → [n6filter]`; `[Auth DB (SQL)] → [REST API, Portal API+GUI]`; `[Auth DB (SQL)] ←→ [Admin Panel]`; `[Auth DB (SQL)] ←→ [n6manage]`. Note: the "`-(AMQP)→`" arrows denote communication via AMQP broker (RabbitMQ).](img/pipeline.png)


## Examining the pipeline

* Run some collector to check data flow.

```bash
(env)$ n6collector_spam404
```

> **Note:** You may want, firstly, to temporarily terminate the corresponding parser (by the command `stop <process>` if *Supervisor* is in use) -- to be able to see (in the RabbitMQ web management panel) incoming messages on the parser's input queue (before they are consumed by the parser).

* Log into the RabbitMQ web management panel to check message queues.
* Log into the *n6* Portal and query the *n6* API through the search form.
* Query the *n6* REST API (you can use *curl*, a web browser etc.).

# Examining Data Flow

!!! warning

    This is a draft document...

This document uses `cert-pl.shield` source to present *n6* data flow.

!!! tip

    You may want to temporarily terminate the source's corresponding parser (by
    running the command `stop <process>` - if [Supervisor](supervisor.md)
    is in use). That way you will be able to see in the RabbitMQ Web Management panel
    incoming messages on the parser's input queue before they are consumed
    by the parser.

    You may also want, for testing purposes, to turn off Supervisor process management and invoke
    subsequent components yourself, examining the data processing by the consumer. 
    For this purpose, terminate all running components `& supervisor> stop all` and delete all 
    queues (in the RabbitMQ web management panel).


To examine the *n6* data flow (see: [n6 Architecture and Data Flow Overview](../../data_flow_overview.md)) do the following:

(A) Create the source-dedicated queue by temporarily running the respective parser (note this: the source-specific collector's output queue is created by running the corresponding parser).

```bash
(env_py3k)$ n6parser_certplshield
```

Then check the created exchange message and the available exchange queues in the RabbitMQ Web Management panel. Available exchange queues should be as follows:

```text
cert-pl.shield
dead_queue
```

Finally, kill the parser process (by pressing `CTRL+C`) so that it will not consume the data from the source-dedicated queue.


(B) Run the corresponding collector and watch as new messages arrive at the `cert-pl.shield` queue. The collector collects the data and then finishes.

```bash
(env_py3k)$ n6collector_certplshield
```

!!! tip

    The lack of events in the source-dedicated queue means that the source is unavailable (check *n6* logs for more information...).


(C) Look up events

1. Log into the *RabbitMQ Web Management* panel to check message queues.
2. Click on the queue name: *cert-pl.shield*.
3. Go to the *Get messages* tab, and set the appropriate number of messages.
4. Click the *Get Message(s)* button. In the *Payload* section, you can read the contents of the queue, which changes with the invocation of the next _n6_ component.
5. Log into the *n6 Portal* and query the *n6* database using the search form.
6. Query the *n6 REST API* (you can use _curl_, a web browser, etc.).


### Data flow

(See also: [n6 Architecture and Data Flow Overview](../../data_flow_overview.md).)

The *n6* pipeline components declare at the RabbitMQ broker two main *topic* exchanges for the data flow:

* `raw` - for messages conveying data from sources, in a raw form (produced by *Collectors* and consumed by *Parsers* via source-dedicated queues as well as by *Archiver* via the `dba` queue).
* `event` - for messages conveying events in *a normalized* (parsed) form (produced by *Parsers* and produced+consumed by other pipeline components).

As noted earlier, the source-dedicated collector's output queue, being the corresponding parser's input queue, is created by running the respective parser.

When the collector is being run, messages containing raw data are sent
to the `raw` exchange - with an appropriate *routing key* which is the
same as the parser input queue's *binding key* -- which, typically, is
the value of the `default_binding_key` attribute of the parser class
(the queue's name is also set to the value of that attribute). This key
consists of two or three segments separated by dots:

* `<source provider>.<source channel>` (e.g., `cert-pl.shield`), *or*
* `<source provider>.<source channel>.<version tag>` (e.g., `cert-pl.shield`);
  the `<version tag>` segment is added when the format of data downloaded
  by the collector changes (i.e., when a new separate parser needs to be
  implemented for the collector).

This way, messages containing data in a raw form will end up in both the
appropriate source-dedicated queue (being the parser input queue) and in
the *Archiver*'s `dba` queue.

*Archiver* stores the obtained data in the *archive database* (NoSQL - *MongoDB*).

The respective parser generates, from the raw data it obtains,
*normalized (parsed) events* and sends them to the `event` exchange with
a *routing key* based on the pattern: `<event type>.parsed.<source
provider>.<source channel>` (where `<event type>` is one of: `event`,
`hifreq`, `bl`) - for example: `event.parsed.cert-pl.shield`.

Further components of the *normalized data* pipeline are:

* **Aggregator** - handles only the `hifreq` (*high frequency*) event type (coming from *Parsers*).
  It aggregates similar events (reducing numbers of output events).
* **Enricher** - tries to enrich incoming events (coming from *Parsers* or *Aggregator*)
  with additional data (like: FQDN, IP address, AS number, country code...).
* **Comparator** - handles only the `bl` (*blacklist*) event type (coming from *Enricher*).
  It treats incoming events as blacklist entries, comparing different
  versions of the concerned blacklist and generating specific events to
  indicate whether there is a new entry is new, or an entry is updated, or
  it should be removed...
* **Filter** - adds to events (coming from *Enricher* or *Comparator*) the `client` attribute,
  whose values are identifiers of *n6* client organizations to whom the
  event is related (belongs to their *inside* access zone).
* **Recorder** - receives the events (coming from *Filter*) and stores them in the *event database*
  (SQL - *MariaDB*).

The input queues of those components have their *binding keys* set to appropriate
values - based on the pattern: `<event type>.<pipeline stage>.*.*`, where:

`<event type>` is one of: `event`, `hifreq`, `bl`;

`<pipeline stage>` is one of:

* `parsed` - matching events coming from *Parsers*,
* `aggregated` - matching events coming from *Aggregator*,
* `enriched` - matching events coming from *Enricher*,
* `compared` - matching events coming from *Comparator*,
* `filtered` - matching events coming from *Filter*;

`*` means that any non-`.` characters will match.

#### Attributes of the parsed events (names correspond to columns in the *event database*):

* **"category"**: Incident category label (some examples: "bots", "phish", "scanning"...).
* **"confidence"**: Data confidence qualifier. One of: "high", "medium" or "low".
* **"restriction"**: Data distribution restriction qualifier. One of: "public", "need-to-know" or "internal".
* **"rid"**: Raw message identifier (given by *Collector*).
* **"source"**: Incident data source identifier.
* **"address"**: Set of network addresses related to the returned incident.
* **"dport"**: TCP/UDP destination port.
* **"name"**: Threat's exact name, such as "virut", "Potential SSH Scan".
* **"time"**: Incident *occurrence* time (**not** *when-stored-in-the-database*).
* **"id"**: Unique event identifier (given by *Parser*).

#### EXAMPLES:

(1) A *raw* message downloaded from the `cert-pl.shield` queue.

```text
Exchange: raw
Routing Key: cert-pl.shield
[...]
type: file
timestamp: 1645450085
message_id: 4cb234876abc76ef9a876ef2765aef82
delivery_mode: 2
headers: meta: http_last_modified: 2022-02-21 13:25:03
content_type: text/csv

Payload
[...]
"2022-02-21 15:05:41","1.2.3.4","443","online","2022-02-21","SomeBot"
"2022-02-21 15:05:35","55.66.77.88","995","online","2022-02-21","SomeBot"
...
...
"2021-01-17 07:44:46","101.102.103.104","4321","online","2022-02-21","Foo Bar"
```

(2) The first of 636 *normalized event* messages from the `enrichment` queue
(with the payload in the JSON format).

```text
The server reported 635 messages remaining.

Exchange: event
Routing Key: event.parsed.cert-pl.shield
[...]
delivery_mode: 2

Payload
[...]
{"category": "cnc", "confidence": "medium", "restriction": "public", 
"rid": "4cb234876abc76ef9a876ef2765aef82", "source": "cert-pl.shield", 
"address": [{"ip": "55.66.77.88"}], "dport": 995, "name": "somebot", 
"time": "2022-02-21 15:05:35", "id": "1ba56823abf239876347865234abc76a"}
```

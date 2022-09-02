# Introduction to the _Parsers_ part

XXX NOT FINISHED!!!

Please, recall the diagram from the beginning of the
_[Collectors](../collectors/index.md)_ part:

![`(External Data) → [Collector] → [Parser] → ...`](../../../img/c_p_pipe.png)

While collectors are _n6_'s entry points for any external data to flow
in, parsers actually analyze those data and translate them to the
_normalized_ format.

To state it more technically: a parser takes input data from its
respective RabbitMQ queue, parses and normalizes those data (converting
them to the _n6_-specific [JSON](https://www.json.org/json-en.html)-based
format), and sends them further down the data processing pipeline (by
pushing those data -- already in their _normalized_ form -- into the
appropriate RabbitMQ exchange).

!!! important

    Whereas collectors may be *stateful*, **parsers shall always be
    *stateless*** (i.e., they should *neither* store any persistent state
    *nor* make use of any external mutable context, such as current time).

## Types of parsers/events

There are three main types of parsers:

- _event_ -- parsing data from ordinary _event_ sources;
- _bl_ -- parsing data from _blacklist_ sources;
- _hifreq_ -- parsing data from _high frequency_ event sources.

For the most parts they work similarly.

The difference which is visible at the first sight is how they tag their
output data, i.e., what they add to the routing key of each message sent
to RabbitMQ. An ordinary _event_ parser just adds the `event.` prefix
to the routing key, a _blacklist_ parser adds the `bl.` prefix, while a
_high frequency_ event parser adds the `hifreq.` prefix.

The routing key is important for the further processing (down the
pipeline). Normal events go through `enricher`, blacklist ones --
through `enricher` and then to `comparator`, and `hifreq` -- to
`aggregator` and only then to `enricher` (see also: the [_n6_ architecture
and data flow](../../../data_flow_overview.md) diagram).

## A _RecordDict_ -- normalized data record

All parsers produce sequences of **_events_** aka **_normalized data
records_**, each being a `dict`-like mapping, containing specific items.

There is a specialized class,
[`n6lib.record_dict.RecordDict`](https://github.com/CERT-Polska/n6/blob/master/N6Lib/n6lib/record_dict.py#L363)
(plus its subclass, `BLRecordDict`, for _blacklist_ data), whose
instances represent _normalized data_ records. A `RecordDict` is a
`dict`-like mapping that provides automatic validation and adjustment of
its items.

Some keys are required to be present in each _normalized data_ record
(i.e., in each `RecordDict` instance when it is serialized): `id`,
`source`, `restriction`, `confidence`, `category` and `time`.

Furthermore, there are lots of optional keys that can appear in a
_normalized data_ record. We do not list all valid `RecordDict` keys
here, but they can be deduced from presence of **`adjust_{key}`**
attributes [in the definition of the `RecordDict`
class](https://github.com/CERT-Polska/n6/blob/master/N6Lib/n6lib/record_dict.py#L645).

## This part's contents

- [Parser Executable Commands](command.md)
- [Parser Base Classes](baseclasses.md)
- [High-Frequency Data Sources](hifreq.md)
- [Parser Tests](testing.md)

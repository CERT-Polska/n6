# Introduction to the _Collectors_ part

XXX NOT FINISHED!!!

Collectors are _n6_'s entry points for any external data to flow in.
Data harvested with a collector are then sent to its corresponding parser.
So the pipeline at this stage looks like this:

![`(External Data) → [Collector] → [Parser] → ...`](../../../img/c_p_pipe.png)

!!! note

    For a broader overview, you may want to take a look at the
    [*n6* architecture and data flow diagram](../../../data_flow_overview.md).

To describe collectors' job more technically: a collector obtains data
from its respective external source (e.g., by downloading files from a
certain security-focused website), and sends them further down the _n6_
data processing pipeline (by pushing those data -- in a form as similar
to the original as possible -- into the appropriate RabbitMQ exchange).

## RabbitMQ-based pipeline

Most of the _n6_ pipeline components -- in particular, all collectors --
send their output data to a [RabbitMQ](https://www.rabbitmq.com/)
message broker instance (using the AMQP 0.9.1 protocol) so that the
pipeline components that are supposed to consume those data (in
particular, the parser corresponding to the given collector) will be
able to take the data from the respective RabbitMQ queue.

## Running a collector

Each collector is run as a separate program (OS process). Depending on
the type of the external source a particular collector is related to, it
may be spawned by a [`cron`-like](https://en.wikipedia.org/wiki/Cron)
scheduler (the most typical way), by a
[`procmail`-like](https://en.wikipedia.org/wiki/Procmail) agent (this
is typical for _e-mail_-based sources) or in some other way.

## Collector base classes

Each collector needs to have a network connection to the RabbitMQ
broker; however, typically, there is no need for you as the programmer
who implements a collector to deal with that stuff directly. There are
several base classes your collector class can derive from which take
care of various repeatable tasks, especially of the stuff related to
initialization of, communication by, and shutting down the RabbitMQ
connection -- so that you can focus solely on your collector's logic.

Those base classes can be found in the `N6DataSources` subdirectory of the _n6_
source code repository, in the
[`n6datasources.collectors.base`](https://github.com/CERT-Polska/n6/blob/master/N6DataSources/n6datasources/collectors/base.py)
module. (The module's file path in the repository is
`N6DataSources/n6datasources/collectors/base.py`.)

### Stateful collectors

Some collectors need to maintain a state, stored between consecutive
collector's runs (for example, to remember the _id_ and creation _time_ of
the last downloaded record, so that, on the next run, the collector will
download and send, as its output, only newer records).

Each class of such a stateful collector needs to refer to its state
that will not be shared with other collectors. The
[`n6datasources.collectors.base.StatefulCollectorMixin`](https://github.com/CERT-Polska/n6/blob/master/N6DataSources/n6datasources/collectors/base.py)
class helps to take care of that.

## This part's contents

- [Collector Executable Commands](command.md)
- [Collector Base Classes](baseclasses.md)
- [Stateful Collectors](state.md)
- [Collector Tests](testing.md)

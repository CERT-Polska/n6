# Introduction to the *Collectors* part

Collectors are *n6*'s entry points for any external data to flow in.
Data harvested with a collector are then sent to its corresponding parser.
So the pipeline at this stage looks like this:

![`(External Data) → [Collector] → [Parser] → ...`](c_p_pipe.png)

> **Note:** For a broader overview, you may want to take a look at
> the [*n6* architecture and data flow](../../../data_flow_overview.md) diagram.

To describe collectors' job more technically: a collector obtains data
from its respective external source (e.g., by downloading files from a
certain security-focused web site), and sends them further down the *n6*
data processing pipeline (by pushing those data -- in a form as similar
to the original as possible -- into the appropriate RabbitMQ exchange).


## RabbitMQ-based pipeline

Most of the *n6* pipeline components -- in particular, all collectors --
send their output data to a [RabbitMQ](https://www.rabbitmq.com/)
message broker instance (using the AMQP 0.9.1 protocol), so that the
pipeline components that are supposed to consume those data (in
particular, the parser corresponding to the given collector) will be
able to take the data from the respective RabbitMQ queue.


## Running a collector

Each collector is run as a separate program (OS process).  Depending on
the type of the external source a particular collector is related to, it
may be spawned by a [`cron`-like](https://en.wikipedia.org/wiki/Cron)
scheduler (the most typical way), by a
[`procmail`-like](https://en.wikipedia.org/wiki/Procmail) agent (this
is typical for *e-mail*-based sources), or in some other way.


## Collector base classes

Each collector needs to have a network connection to the RabbitMQ
broker; however, typically, there is no need for you, as the programmer
who implements a collector, to deal with that stuff directly.  There are
several base classes your collector class can derive from which take
care of various repeatable tasks, especially of the stuff related to
initialization of, communication by, and shutting down the RabbitMQ
connection -- so that you can focus solely on your collector's logic. 

Those base classes can be found in the `N6Core` subdirectory of the *n6*
source code repository, in the
[`n6.collectors.generic`](https://github.com/CERT-Polska/n6/blob/master/N6Core/n6/collectors/generic.py)
module. (The module's file path in the repository is
`N6Core/n6/collectors/generic.py`.)

### Stateful collectors

Some collectors need to maintain a state, stored between consecutive
collector runs (for example, to remember the *id* and creation *time* of
the last downloaded record, so that, on the next run, the collector will
download and send, as its output, only newer records).

Each class of such a stateful collector needs to refer to its own state
that will not be shared with other collectors.  The
[`n6.collectors.generic.CollectorWithStateMixin`](https://github.com/CERT-Polska/n6/blob/master/N6Core/n6/collectors/generic.py#L124)
class helps to take care of that.


# The *Collectors* part's chapters

* [Collector Executable Commands](command.md)
* [Collector Base Classes](classes.md)
* [Stateful Collectors](state.md)
* [Collector Tests](testing.md)

# Collector Base Classes

This section takes a quick look at each of the possible base classes
of your collector to choose from. Each subsection will familiarize you 
with a new class, starting from an abstract interface and then
discussing more specialized ones.

Each description has a step by step implementation guide which shows
how to implement your own collector using one of those classes as 
its base.

Definitions for every class described here can be found in the `N6Core`
library in the `n6.collectors.generic` module (along with some
documentation in docstrings).


## AbstractBaseCollector

`AbstractBaseCollector` is a general interface for the collectors' implementation in the
`n6.collectors.generic` module. However, it should only be used in special cases
such as implementing a new base class for collectors to derive from.

When deriving from this class it is important to remember that it does
not handle, by itself, the communication with the event queue.

The interface consists of four methods (two of which are abstract and have to be overridden):

* `get_script_init_kwargs` - a class method returning a dictionary which will be then 
passed in as the keyword arguments the collector constructor (when collector initialization has
been started from the generated console command; see section _Collector command_). 
The default implementation returns an empty dictionary.
* `run_handling` - starts a collector and takes care of exiting with `Ctrl+C`.
Default implementation calls `run` method end expects that it either returns gracefully, or raises `KeyboardInterrupt` exception (caused by `Ctrl+C`)
upon which it calls the `stop` method.
* `run` - abstract method which should contain the main collector's activity.
* `stop` - abstract method which should clean-up after interruption of the collector's activity (the case of `KeyboardInterrupt` propagated from `run`).

### Implementation based on AbstractBaseCollector

Unless there is some really special case you probably 
should not implement your collector as based on this interface alone.
You would need to deal with the queue communication
by yourself as well as be wary about *n6*'s queue naming
conventions, exchange types and so on...

Next class described in this chapter will address these issues
so you should not have to bother with them.

But if you really have to use `AbstractBaseCollector` as your
direct base then just implement the `run` and `stop` methods.

## BaseCollector

`BaseCollector` is the implementation of the `AbstractBaseCollector`, with
configuration and the queue communication already handled.
It achieves this by deriving from the `QueueBase` (see appendix for the `QueueBase` class) and `CollectorConfigMixin` classes. 

`CollectorConfigMixin` is a subclass of `ConfigMixin`. The indirection
is needed to provide backwards compatibility with some of the older
collectors which used older configuration format; besides that the
`CollectorConfigMixin` adds two helper methods: `set_configuration`
(called on initialization of most collectors) and
`get_config_spec_format_kwargs` (called from `set_configuration`;
overridden by some collectors).

### Implementation based on the BaseCollector

Here is how you would implement your own collector
when using `BaseCollector` as your parent class.

#### Defining the collector's type

Start by creating empty implementation like so:

```python
class MyCollector(BaseCollector):

    type = 'stream'  # Could be one of 'stream', 'file', 'blacklist'.

```

The `type` class attribute tells *n6* what kind of data our collector
will publish to the RabbitMQ `raw` queue.

* The `stream` type represents relatively small data objects in the `json`
  (or `bson`) format, each ready to be saved in *MongoDB* as a document.
 
* The `file` type represents (possibly large) data in any format. Data
  bigger than 16MB must use the `file` type.

* `blacklist` type is special. It tells *n6* that data are gathered
   from a blacklist source, so it should be stored in a form of
   diff-like deltas.

   What is important about `blacklist` data is
the fact that they have different processing pipeline than
normal data. Normal data go like so (aggregator
is in parenthesis as it only takes part in the high-frequency
data processing, more on that later):

```
source -> collector -> parser -> (aggregator ->) enricher -> filter -> recorder 
```

...while the `blacklist`-data-specific pipeline looks like so:

```
source -> collector -> parser -> enricher -> comparator -> filter -> recorder
```

As it is expected from `blacklist` data to *gradually change* over time,
collectors gathering them can just download and pass them on to the
pipeline.

On the other hand, for collectors of the other types (non-`blacklist`
ones) it is often not so trivial because, typically, sources expose
data that are continually increasing in records over time - so a
collector must take care not to download the same records again and
again; to cope with that such collectors need to have some internal
state that persists throughout collector's runs. Because of that it is
often a bit harder to implement a `stream` or a `file` collector than a
`blacklist` one.

#### Customizing output queue

There is the class attribute `output_queue` which allows us to customize
the collectors output in relation to RabbitMQ queues.
We will not cover it in details here but if, for example, you
wanted to have two output queues (instead of the default one) you could
define that like so:

```python
output_queue = [
    {
        'exchange': 'raw',
        'exchange_type': 'topic',
    },
    {
        'exchange': 'sample',
        'exchange_type': 'topic',
    },
]
```

If left unchanged `output_queue` defaults to:

```python
output_queue = {
    'exchange': 'raw',
    'exchange_type': 'topic',
}
```

#### Defining configuration file structure

As `BaseCollector` derives from the `CollectorConfigMixin` class 
we can use its capabilities to define config file structure using a
special syntax. To do so we need to assign our configuration specification
as the string to the `config_spec` class attribute. It is easier 
to show it rather than to explain it.

So our class would look like so:

```python
class MyCollector(BaseCollector):

    type = 'stream'  # Could be one of 'stream', 'file', 'blacklist'.

    config_spec = '''
        [my_collector_sec]
        source :: str
        url :: str
        download_retries = 1 :: int
    '''
```

In the code above we first line of the *config spec* specifies in the
square brackets what is the name of our configuration section inside of
a configuration file. Then we can define attributes followed by
*converter* tags specifying value types (see the `n6lib.config.Config`
module for the details). We can also specify default values as we did
with the `download_retries` attribute.

We can then retrieve our attributes from the `config` dictionary when
needed:

```python
class MyCollector(BaseCollector):

    type = 'stream'  # Could be one of 'stream', 'file', 'blacklist'.

    config_spec = '''
        [my_collector_sec]
        source :: str
        url :: str
        download_retries = 1 :: int
    '''

    def __init__(self, **kwargs):
        # we don't really need to save it as an instance 
        # attribute but here we do so just as an example
        self._url = self.config['url']
```

Some of the configuration fields are used by the parent classes, in
this case the `source` field is a field required by the `BaseCollector`
class. (Note: this field should be *the first part* of the data source identifier.)

As you can see it is important to know what kind of configuration
attributes your base class might need to have defined.

There is an older way of defining configuration structure using
`config_group` and `config_required` class fields but those are
deprecated. Still, you could find them in implementations of some
existing collectors.

#### Collector's logic

What the `BaseCollector` class does for us is dividing collectors logic
into 6 different methods. The method `get_output_components` glues them
back together (yes, it is a *template method* - if you are familiar
with programming design patterns). Its return value contains all you
need to export the collected data as a RabbitMQ message; it is a
3-tuple consisting of: the AMQP routing key, the output data body and a
dict of AMQP message properties (typically, these three items are ready
to become respective arguments of the `publish_output` method).

The methods we (may) want to concern ourselves with are as following:

* `process_input_data`
* `get_source_channel`
* `get_source`
* `get_output_rk`
* `get_output_data_body`
* `get_output_prop_kwargs`

We will cover all of them.

`process_input_data` may take some input data (dict of arbitrary
keyword arguments -- whatever has been passed into the call of
`get_output_components`; often there is no one) and can enrich or
replace them if needed. The resultant dict is then passed as keyword
arguments to *each* of the later functions' calls. The default
implementation just returns the given keyword arguments intact.

`get_source_channel` returns the second part of the source identifier.
Here we need to explain it precisely: each source identifier follows
the following format: `{provider name}.{channel name}` (each of the two
parts must consist of ASCII letters, digits and hyphens only; and whole
identifier must not be longer than 32 characters). So, for example, the
identifier of a source whose owner's name is *LegitBL* and that
provides information about TOR exit nodes could be `legit-bl.tor`. This
method should return the source's channel part (in the case of this
example it would be `'tor'` ). **This method needs to be overridden in
subclasses** as the default implementation raises `NotImplementedError`.

`get_source` returns whole source identifier as specified above. For
most collectors you can just leave the default implementation which
uses the `source` option from the collector's configuration; so you
should specify that option in `congig_spec`.

`get_output_rk` returns collector's routing key and, as with the
previous method, the default implementation should suffice.

`get_output_data_body` is arguably the most important method. Returns
collector's output message data body. In many cases this is the place
where most of the collector's logic is placed. **This method needs to
be overridden in subclasses** as the default implementation raises
`NotImplementedError`.

`get_output_prop_kwargs` returns a dictionary of custom keyword
arguments for the `pika.BasicProperties`. If the dictionary needs some
refinements a subclasses should *expand* this method using `super()` -
as the dictionary produced by the default implementation rather should
not be discarded/replaced completely.

So for the needs of really simple collector we would need to override just
the two of the above methods: `get_source_channel` and `get_output_data_body`.

What we also need is to implement the `start_publishing` method (a
`QueuedBase` hook) in which we need to call at lest the following three
methods:

* `get_output_components` - described above,
* `publish_output` (defined in the `QueuedBase` class) - publishes our data to the output queue(s),
* `inner_stop` (defined in the `QueuedBase` class) - signals to the RabbitMQ connection machinery that it is time to leave the connection's event loop (so that the collector will exit gracefully).

See the following example:

```python
from n6.collectors.generic import BaseCollector


class MyCollector(BaseCollector):

    type = 'stream'  # Could be one of 'stream', 'file', 'blacklist'.

    config_spec = '''
        [my_collector_sec]
        source :: str
        url :: str
        download_retries = 1 :: int
    '''

    def __init__(self, **kwargs):
        # we don't really need to save it as an instance 
        # attribute but here we do so just as an example
        self._url = self.config['url']

    def start_publishing(self):
        for download_option in ['foo', 'bar']:
            (output_rk,
             output_data_body,
             output_prop_kwargs) = self.get_output_components(download_option=download_option)
            self.publish_output(output_rk, output_data_body, output_prop_kwargs)
        self.inner_stop()        

    def get_source_channel(self, **processed_data):
        return 'tor'  # just exemplary source channel we could use

    def get_output_data_body(self, download_option, **kwargs): 
        data = self._download_data(self._url, download_option, **kwargs)
        assert isinstance(data, bytes) 
        return data

    def _download_data(self, url, download_option, **kwargs):
        # Here we implement data collection
```

### Remarks

The implementation shown above is really simplified for the purpose of
the example. In particular, as said before, `stream` and `file`
collectors usually have to keep track of the data they already have
collected maintaining some persistent state to prevent collecting them
again.

Implementing collectors with persistent state will be discussed in the
`Collector's state` chapter of this guide.

## A roadmap for extension of this guide...

In the `n6.collectors.generic` module a few noteworthy, more
specialized, collector base classes are also defined:

* `BaseOneShotCollector`,
* `BaseEmailSourceCollector`,
* `BaseTimeOrderedRowsCollector`
* `BaseDownloadingCollector`,
* `BaseDownloadingTimeOrderedRowsCollector`.

They are to be described in the future version of this guide...
 
(Also, a few more collector base classes are defined in that module --
but those ones are just a legacy stuff and should not be used to
implement new collectors.)

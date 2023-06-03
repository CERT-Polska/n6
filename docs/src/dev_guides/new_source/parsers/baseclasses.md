# Parser Base Classes

As with the collectors, _n6_ already comes with some tools
to relieve the developer of some work that needs to be done
when implementing a new parser, like modifying a routing key.

There are three classes to choose from, one for each of the parser types:

- `BaseParser`,
- `AggregatedEventParser`,
- `BlackListParser`.

Their names speak for themselves. All of them can be found in the
`n6datasources.parsers.base` module in the `N6DataSources` library.

(Truth be told, there are more than just three, but those others
are considered legacy and should not be used in any new code.)

## Configuration

Each parser has its configuration.
Simple parsers will only have one attribute
which is `prefetch_count` (setting it to "1" should
work in most basic cases).

Content of the configuration file could look like so:

```
[MyOwnParser]
prefetch_count = 1
```

In _n6_ source code repository, the templates of all configuration files
for the collectors and parsers are stored in the
`N6DataSources/n6datasources/data/conf` directory and their names start
with `60_` followed by the source provider name and suffixed with
`.conf` (e.g., `60_example.conf`). If a source has the collector and the
corresponding parser, then the configuration for the collector and the
parser should be, by convention, in the same file.

## Implementation based on BaseParser

When implementing parser using `BaseParser` as our
parent class, we need to specify some class attributes as well
as implement the `parse` method. `BaseParser` has
more methods that ease implementing some
special corner cases, but for a generic source this one
should be sufficient.

There are two (or three, see section _Versioning parsers_)
attributes we care about:

- `default_binding_key` - the routing key by which the parser will
  draw its data from the queue. Typically, it consists of two parts joined
  with the "." character. The first part is the source name (provider) and the second
  one is the source channel. So for the `example-provider` source provider and
  the `example-channel` source channel, it would look like so:
  `default_bindig_key = "example-provider.example-channel"`.
- `constant_items` - which is a dictionary of items that
  are constant for all of the output events. Most parsers will have
  a dictionary of at least 3 items `restriction`, `confidence` and
  `category`.

The `parse` method takes only one positional argument (apart from `self`):
`data` (a dict containing, among others, the actual input data),
and - as we can have multiple events from one chunk of data (e.g. a CSV-formatted rows with one event per row) -
yields consecutive events as dict-like objects.
Remember that `data` contains staff that was taken from the input queue, so
there are some additional properties like `timestamp` and so on.
What is most important, the actual input content is stored under the `raw` key
(typically, it is exactly what was sent by the collector as the _output
data body_).

Example data:

```json
[
  {
    "properties.app_id": null,
    "properties.cluster_id": null,
    "properties.content_encoding": null,
    "properties.content_type": null,
    "properties.correlation_id": null,
    "properties.delivery_mode": null,
    "properties.expiration": null,
    "properties.message_id": "0123456789abcdef0123456789abcdef",
    "properties.priority": null,
    "properties.reply_to": null,
    "properties.timestamp": "2019-11-10 10:14:00",
    "properties.type": "foo...bar...",
    "properties.user_id": null,
    "raw": "{\"tag\": \"example.com,some1.2019-10-11T23:59:59\"}",
    "raw_format_version_tag": null,
    "source": "example-provider.example-channel"
  },
  {
    "properties.app_id": null,
    "properties.cluster_id": null,
    "properties.content_encoding": null,
    "properties.content_type": null,
    "properties.correlation_id": null,
    "properties.delivery_mode": null,
    "properties.expiration": null,
    "properties.message_id": "0123456789abcdef0123456789abcdef",
    "properties.priority": null,
    "properties.reply_to": null,
    "properties.timestamp": "2019-11-10 10:14:03",
    "properties.type": "foo...bar...",
    "properties.user_id": null,
    "raw": "{\"tag\": \"example.org,some2.2019-10-12T01:02:03\"}",
    "raw_format_version_tag": null,
    "source": "example-provider.example-channel"
  }
]
```

So some very simple implementation could look like so:

```python
class MyOwnParser(BaseParser):

    default_binding_key = "example-provider.example-channel"

    constant_items = {
        'restriction': 'public',
        'confidence': 'medium',
        'category': 'server-exploit',
    }

    def parse(self, data):
        raw = json.loads(data['raw'])
        for event in raw:
            with self.new_record_dict(data) as parsed:
                tag_parts = event['tag'].split(',')
                parsed['fqdn'] = tag_parts[0]
                parsed['name'] = tag_parts[1]
                parsed['time'] = tag_parts[2]
                yield parsed
```

In the example we see that the helper method `new_record_dict`
(which creates an instance of `n6lib.record_dict.RecordDict`, which is
a dict-like mapping class with some validation and adjustment capabilities added).
It is used with the `with` clause as it sets the exception
handle callback as the `handle_parse_error` method of the `BaseParser`
which can be overridden by the deriving classes (for example, a class deriving from
`SkipParseExceptionMixin` will suppress most errors...).

## Implementation based on the BlackListParser

Implementing a blacklist parser works mostly the same as implementing a generic one.
There are just some additional class attributes to specify if needed.

The blacklist event has some private data added for the _Comparator_
module to use, and we need to help the parser find the values it needs.

The data we need to find is the time of the event.
There are three attributes we can set:

- `bl_current_time_regex_group`,
- `bl_current_time_regex`,
- `bl_current_time_format`.

If none of those will be set by the subclass, the time will be taken
from the `properties.timestamp` key in the data. If the collector's
input is an e-mail then the time will be taken from the key
`mail_time` in the dictionary stored under the `meta` key in the
top-level `data` dictionary; if it is a website then the time will be
taken from the key `http_last_modified` from the same dictionary (it is
the responsibility of appropriate collectors to place that data in the
`meta` header of the AMQP message being sent to the RabbitMQ queue).

If `bl_current_time_regex` is specified, then the
parser will search for the match in the `data['raw']`.
If the match is found, it will capture the time
using the `bl_current_time_regex_group`, which defaults
to `'datetime'`. Lastly, the parser assumes that
the data extracted this way will be in the iso format.
If that is not correct, then the `bl_current_time_format`
should be set to the value which will be used
as the format when calling `datetime.strptime` on the
extracted string.

## Implementation based on the AggregatedEventParser

Implementation is the same as the `BaseParser`, except it needs to create
a `_group` key for the _Aggregator_ module
-- so the `group_id_components` class attribute needs to be provided.
See [high frequency data sources](hifreq.md).

Example:

```python
class ExampleHiFreqParser(AggregatedEventParser):

    default_binding_key = 'example-provider.example-channel'
    constant_items = {
        'restriction': 'public',
        'confidence': 'low',
        'category': 'tor',
    }
    group_id_components = 'ip', 'dport', 'proto'

    def parse(self, data):
        # implementation here...
        pass
```

## Versioning parsers

A little disclaimer about the `default_binding_key`'s value.
We said before that the key consists of two parts separated with the "." character,
but it can be three sometimes. The full format of the default binding key looks
like so: `{source provider}.{source channel}.{raw_format_version_tag}` - with the provision that
the last part is optional.

So what is this `raw_format_version_tag`?
When the format of the data provided by some external source changes
we need to implement a new or modify the old collector.
However, for the archivers sake (it can recover our data, but the
data are kept raw from the collectors, so they need to be parsed
again upon recovery) we need to keep the old parser unchanged.
So we need to somehow say to the _n6_ that the source is
the same, it's just a newer version. That's when the
`raw_format_version_tag` comes into play.

If needed, we set the version tag inside our new (or modified)
collector (as the `raw_format_version_tag` attribute) and then add it to the `default_binding_key`
of our new parser. So, for example, if we would
use the `raw_format_version_tag` in format `YYYYMM`
(which is a handy convention; we imply that the source does not change its format often)
then, if the source has changed, the collector would
look like so:

```python
# Modified collector
class ExampleSourceCollector(BaseCollector):

    raw_type = 'stream'

    raw_format_version_tag = '201912'

    config_spec = '''
        config spec here
    '''
    # methods implementation below skipped
```

The parsers:

```python
# Old parser implementation
class ExampleSourceParser(BaseParser):

    default_binding_key = 'example-provider.example-channel'

    # implementation skipped

# New parser
class ExampleSource202112Parser(BaseParser):

    default_binding_key = 'example-provider.example-channel.201912'

    # implementation skipped
```

## Remarks

This document is just a draft and only covers the most basic
implementation. To learn more about how parsers work and
see some examples, look into the `base.py` module inside
the "parsers" directory, or implementation of any
parsers that can be found here.

# High-Frequency Data Sources

Some data sources have the property of supplying high amounts of
events that are very similar to each other (for example
differing only in timestamps). For these events, we do not want to
store each one in the database separately as it would
take up a lot of space. What we care about is the original data
of the first event (because the rest is just the same), the time
of the first event, the time of the last event, and the count of
events of this kind we got.

## Aggregator module

Data from these kinds of sources should go through the `aggregator`
module. What it does is what we wanted in the first place.
It keeps the data of the first event, counts how many
we got up to this point and keeps track of the time
of the first and the last event. What's more, it periodically
takes all of its stored events and sends them to the database
so that they will not be kept by it forever
(actually the process of sending the aggregated events as
one event to the database is a bit more complicated than just doing
it once per several hours, but we can safely skip the details).

## Sending data to the Aggregator

To send the data to the `aggregator` the parser needs
to add the `hifreq` tag at the beginning of the routing key
of the message as well as add a special `_group` key
to the payload (it would be possible to do it in the collector,
but it is much better to do so in the parser
because the collector should not know if the source is
a high frequency one or not).

How does `aggregator` know it should treat the
event the same way it treated the last one? Precisely by
the value under the `_group` key. If `_group` values of some two
events are the same, the events are treated as incarnations of the same event, just with
different timestamps.

What is more, the `event_type` attribute of the parser class should be
set to `'hifreq'`.

### AggregatedEventParser

`N6DataSources` provides a base class for the parsers of the high frequency
data sources. The title of this section already spoiled the
name, it is `AggreagatedEventParser`.

It takes care of most of the things like setting the `event_type` class attribute
and generating the value for and adding the `_group` key to the
payload as well as modifying the routing key appropriately.

The value for the `_group` key will be created by getting the values
for the keys specified in the `group_id_components` class attribute and
joining them with underscores. The values will be taken from the
incoming collector's data. If one of the given keys is missing from the
data, the `None` string value will be used in place of it. However, at
least one of the specified keys must be present, otherwise `ValueError`
is raised.

It is also important to note that an `ip` key is treated
differently. It actually evaluates to `data['address'][0]['ip']`.
It may look strange, however, it is a really frequent pattern in the
collected data, so it was done to make it simpler for the implementation.

Remember that you still need to implement the `parse` method yourself.

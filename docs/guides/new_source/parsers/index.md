# Parsers

Parsers take data from their respective queue and normalize them.
There are three main types of parsers:

* Event - parsing data from event sources.
* Blacklist - parsing data from blacklist sources.
* Hi-Freq - parsing data from high frequency event sources.

For the most parts they work really similar. The most 
important difference between them is how they tag their
output data (what do they add to the routing key of the message).
An ordinary event parser just adds the
`event` string at the start of the routing key,
Blacklist parser adds the `bl` string, while 
the high frequency parser adds the `hifreq` string.

The routing key is important for the further processing down the
pipeline. While normal events go through `enricher`, blacklist ones -
through `enricher` and then to `comparator`, and `hifreq` - to
`aggregator` and only then to `enricher`.

One more thing to note here is that a parser does not have to
receive data from the collectors.
Parsers only draw from their respective queue
but how the data got there is not for their concern.
It could be pushed there with some other tool. 

## Parsers' output

Parsers normalize data for the *n6* so the output of the
parser cannot be of any format. All parsers need to return
a dictionary of specific items. There is a specialised
class called `RecordDict` (and `BLRecordDict` for blacklist parsers)
which is an enhanced dictionary, intended to be used
to represent *n6*'s records. 

Some fields of the returned dictionary
are required by the *n6* in the
resulting data. These fields are
`id`, `source`, `restriction`, `confidence`, `category`, and `time`.
Furthermore there are a lot of optional
fields that the values can be provided for.
The full list the fields that can appear in the parser's result can be
deduced from the `adjust_{field name}` attributes of the
`n6lib.record_dict.RecordDict` class.

Contents
--------

* [Console command](command.md)
* [Base classes](baseclasses.md)
* [Hi-Freq data sources](hifreq.md)
* [Testing](testing.md)




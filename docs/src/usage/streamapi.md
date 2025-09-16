<style>
  code.language-bash::before{
    content: "$ ";
  }
  code.language-bashcmd::before{
    content: "$ ";
  }
</style>


# *n6 Stream API*

The API described in this document complements [*n6 REST API*](restapi.md).
The *Stream API* makes it possible to receive events asynchronously, in
near real-time. The JSON-based data format is similar to the one used in
the *REST API* (but there are a few differences, see [*Data
format*](#data-format) below...).


## Transport layer

*n6 Stream API* is based on STOMP ([Simple Text Oriented Message
Protocol](https://stomp.github.io/)).

Connections are authenticated using the following credentials:

- `username` -- the *n6* user's **login** (being an e-mail address);
- `passcode` -- the *n6* user's **API key** (the same which can be used
  to authenticate to *n6 REST API*; a user can generate a new *API key*
  through *n6 Portal*).

In the case of the CERT Polska's instance of *n6*, the address of the STOMP
server is **`n6stream.cert.pl:61614`**.

The supported STOMP versions are: *1.0*, *1.1* and *1.2*. The use of
[TLS](https://en.wikipedia.org/wiki/Transport_Layer_Security) is
mandatory. We recommend using the most recent version of the protocol
(STOMP *1.2*) and of the [OpenSSL](https://openssl-library.org/) cryptographic
library.

To receive data, the client must subscribe to an appropriate STOMP destination.
The client uses the destination header to define which of the available events
should be delivered through the connection. The format can be described with
the following [ABNF](https://datatracker.ietf.org/doc/html/rfc2234) syntax rule:

```
destination = "destination:/exchange/" org-id "/" resource "."
              category "." source-provider "." source-channel
```

-- where:

- **_org-id_** is the client's organization identifier (the user organization's
  domain name registered in the *n6* system).

- **_resource_** identifies the desired scope of data to be retrieved. Available
  *resources* are:
    - `inside` (analogous to *REST API*'s `report/inside`) -- the stream of
      events related to the client's organization networks/services;
    - `threats` (analogous to *REST API*'s `report/threats`) -- the stream of
      general threat indicators, typically shared with other organizations,
      i.e., not particularly related to the client's organization
      networks/services; can be useful, e.g., for blocking rules.

- **_category_** is one of the possible values of the events' `category` attribute
  (see the description of that attribute in [the relevant section of the *REST
  API* documentation](restapi.md#event-attributes)).

- **_source-provider_** and **_source-channel_** are the two dot-separated
  components of an event's `source` attribute which identifies the *data source*
  the event originates from (where *source provider* is the label of a group
  of data sources that are, typically, provided by a certain organization
  or person; and *source channel* is the label of a specific data feed).

Except *org-id*, each of the variables can be substituted by an asterisk (`*`),
which matches any value.


## Data format

Each STOMP message returned by the server contains a single *n6* event in the
[JSON](https://www.json.org/json-en.html) format.

All event attributes described in the [*REST API*
documentation](restapi.md#event-attributes) can appear in events emitted
by the *Stream API*, **except for the `modified` and `status`
attributes**

**Additionally**, each event has a **`type` attribute**. Its value is one of:

- `"event"` -- meaning that the event is an ordinary one (or, for certain
  data sources, one being the initial event of an aggregated series of
  high-frequency events; for simplicity, however, no updates regarding
  such aggregated series are emitted by the *Stream API*);

- `"bl-new"` -- meaning that the event represents a new blacklist entry;

- `"bl-update"` -- meaning that the event represents an update of the
  expiration time (`expires`) of a blacklist entry that was emitted
  earlier; the event's `id` is the `id` of that earlier one;

- `"bl-delist"` or `"bl-expire"` -- meaning that the event represents
  the removal/expiration of a blacklist entry that was emitted earlier;
  the event's `id` is the `id` of that earlier one;

- `"bl-change"` -- meaning that the event represents, for a blacklist
  entry that was emitted earlier, a change to any attribute except the
  expiration time (`expires`); this new event has a new `id`, and its
  `replaces` is the `id` of that earlier event (which should be considered
  as superseded by the new one).


## Examples

### Example 1

Subscription to all available events for organization `example.org`
(no filtering):

```
SUBSCRIBE
destination:/exchange/example.org/*.*.*.*

^@
```

!!! tip

    `^@` is a terminal escape sequence for NULL (ASCII 0x00), which signals the
    end of a STOMP frame. Common keyboard shortcut `Ctrl` + `Shift` + `2`.

Example message from the server (lines wrapped for readability):

```
MESSAGE
destination:/exchange/clients/inside.bots.hidden.42
message-id:Q_/exchange/example.org/inside.#@@session-FO2N7aFVkvfmTQK_4A@@1
redelivered:false
n6-client-id:example.org
persistent:1
content-length:431
{"id": "392ab73bbe7bcd6a56c84af2234987a4", "source": "hidden.42",
 "restriction": "need-to-know", "confidence": "medium", "category": "bots",
 "time": "2024-05-04T10:59:03Z", "address": [{"ip": "203.0.113.42", "cc": "PL",
 "asn": 1234}, {"ip": "203.0.113.123", "cc": "PL", "asn": 1234}],
 "adip": "x.x.51.198", "dport": 22, "name": "avalanche-andromeda",
 "origin": "sinkhole", "proto": "tcp", "sport": 58362, "type": "event"}
```

### Example 2

STOMP *destination* to receive only events representing indicators of
malware infections (category "bots") within the client's organization
network(s), regardless of what data sources the events originate from:

```
destination:/exchange/example.org/inside.bots.*.*
```

### Example 3

Using an OpenSSL command line tool to connect to the server, authenticate
and subscribe:

```bashcmd
openssl s_client -connect n6stream.cert.pl:61614

CONNECT
login:mylogin@example.org
passcode:<here API key generated via n6 Portal>

^@

SUBSCRIBE
destination:/exchange/example.org/*.*.*.*

^@
```

!!! tip

    Typically, you have only a few seconds to send a `CONNECT` frame before
    the connection is automatically closed.

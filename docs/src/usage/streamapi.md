# n6 Stream API

The stream API complements the REST API of the n6 platform. The stream API
allows to receive events asynchronously, near real-time. The JSON data format is
identical with the one used in the REST API (with a single exception: see next
sections).

## Transport layer

The stream API is based on STOMP (Simple Text Oriented Message Protocol).

Connections are authenticated by the following credentials:

* `username` -- the *n6* user's **login** (being an e-mail address);
* `passcode` -- the *n6* user's **API key** (the same which can be used
  to authenticate to the *n6* REST API; a user can generate their *n6*
  API key by their own via the *n6* Portal).

Address of the STOMP server: **n6stream-new.cert.pl:61614**

Supported STOMP versions: 1.0, 1.1, 1.2. TLS is mandatory. We recommend to
use the most recent version of the protocol (1.2) and the OpenSSL cryptographic
library.

To receive data from *n6*, the client must subscribe to an appropriate STOMP
destination. The client uses the destination header to define which of the available
events should be delivered through the connection. The format is as follows (ABNF
syntax):

```
destination = "destination:/exchange/" id "/" resource "."
category "." source-provider "." source-channel
```

Meaning of the variables:

- **id**: *n6* client organization identifier (the user organization's domain name
  registered in the *n6* system)
- **resource**: analogous to the REST API resource, can take one of the following
  values
  - `inside`: events that occurred within the client’s network
  - `threats`: data on threats relevant to the recipient, might not be present
    in the client’s network (e.g. command and control servers)
- **category**: equal to value of the category field in events
- **source-provider** and **source-channel**: the two components of the
  identifier of the source of the information (*source provider*: the
  label of a group of sources which is, typically, provided by one
  organization or person; *source channel*: the label of a specific feed)

Except id, each of the variables can be substituted by an asterisk (\*), which matches
any value.

## Data format

Each STOMP message corresponds to a single *n6* event in JSON format. All
attributes described in the REST API documentation are available in the stream
API with identical semantics.

Additionally, there is a **type** attribute that can take following values:

- event: a single event
- bl-new: new blacklist entry
- bl-update: update of the expiration time for a blacklist entry
- bl-change: change of any attribute except expiration time for a blacklist entry
- bl-delist: removal of a blacklist entry

## Examples

### Example 1

Subscription to all available events for organization `nask.pl` (no filtering):

```
SUBSCRIBE
destination:/exchange/nask.pl/*.*.*.*

^@
```

!!! tip

    `^@` is a terminal escape sequence for NULL (ASCII 0x00), which signals the
    end of a STOMP frame. Common keyboard shortcut `Ctrl` + `Shift` + `2`.

Message from the server (lines wrapped for readability):

```
MESSAGE
destination:/exchange/clients/inside.bots.hidden.48
message-id:Q_/exchange/nask.pl/inside.#@@session-FOUv4xFVkvfMtmK_4A@@1
redelivered:false
n6-client-id:nask.pl
persistent:1
content-length:263
{"category": "bots", "origin": "sinkhole", "confidence": "medium",
"name": "slenfbot", "address": [{"cc": "PL", "ip": "10.20.30.40",
"asn": 8308}], "source": "hidden.48", "time": "2015-08-28T09:32:05Z",
"type": "event", "id": "0f56ebba9129003dc6192e72eef50e70"}
```

### Example 2

STOMP _destination_ used to receive only information about malware infections
(category "bots") within the protected network, regardless of the original data
source:

```
destination:/exchange/nask.pl/inside.bots.*.*
```

### Example 3

Connecting to the server using OpenSSL command line tools, authenticate and subscribe:

```
openssl s_client -connect n6stream-new.cert.pl:61614

CONNECT
login:<login@domain.com>
passcode:<APIKEY_generated_from_n6Portal>

^@

SUBSCRIBE
destination:/exchange/domain.com/*.*.*.*

^@
```
!!! tip

    You have few seconds to send CONNECT frame before connection close automatically.


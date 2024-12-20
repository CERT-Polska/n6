# n6 REST API

The API described in this document is the *n6* system's main interface
to share security information with external systems and applications.
The interface takes the form of a simple REST-style service, based on
the HTTP(S) protocol.


## Overview

*n6* uses an *event*-based data model to represent all types of security
information. Each *event* can be represented by a JSON object with a set
of mandatory and optional attributes -- such as: `time`, `category`,
`address`, `fqdn`, `origin`... (see the [*Event Attributes*](#event-attributes)
section below)

*n6 REST API* makes it possible to retrieve any event data to which the
client's organization is authorized to access.


### Request

Only [*GET*](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/GET) requests are supported.

#### Authentication

The API's authentication mechanism is based on *API keys*. Your *API
key* needs to be sent in an HTTP `Authorization` header, using the
*Bearer* schema (the value of the header should look like the following:
`Bearer YOUR-API-KEY`). You can generate a new *API key* through *n6
Portal*.

#### URI

The *n6 REST API*'s URI scheme can be described with the following
[ABNF](https://datatracker.ietf.org/doc/html/rfc2234) syntax rule:

```
uri = "https://" server "/" resource "." format "?" query
```

-- where:

- **_server_** is the API server's fully qualified domain name (*note*:
  it is `n6api.cert.pl` in the case of the CERT Polska's instance of *n6*).
- **_resource_** identifies the desired scope of data to be retrieved.
  Available *resources* are:
    - `report/inside` -- events related to the client's organization
      networks/services (only visible to this organization);
    - `report/threats` -- general threat indicators, typically shared
      with other organizations, i.e., not particularly related to the
      client's organization networks/services; can be useful, e.g., for
      blocking rules;
    - `search/events` -- global search (*note:* this one is not available
      in the case of the CERT Polska's instance of *n6*).
- **_format_** is the requested format, such as `json`, `sjson` or `csv`.
- **_query_** (described in the [next subsection](#query)) specifies
  which events are to be retrieved.

#### Query

Generally, the *query* part of a URI defines a list of conditions on
selected event attributes.

Its syntax can be described using the following
[ABNF](https://datatracker.ietf.org/doc/html/rfc2234) rules:

```
query           = parameter *("&" parameter)
parameter       = name "=" value-or-values
value-or-values = value *(comma value)
comma           = "," / "%2C"
                ; bare or percent-encoded comma character
```

-- where:

* **_name_** identifies one of the valid query parameters -- see the
  [*Query Parameters*](#query-parameters) section below.
* **_value_** of a query parameter is a
  [UTF-8](https://datatracker.ietf.org/doc/html/rfc3629#section-3)
  string which may consist of any characters except `,` (comma),
  provided that all non-"safe" characters are
  [*percent-encoded*](https://datatracker.ietf.org/doc/html/rfc3986#section-2.1).
  (To be more precise: the "safe" characters that never require such
  encoding are: `A-Z`, `a-z`, `0-9`, `-`, `.`, `_` and `~`; also
  unencoded `:` is acceptable in this context. To keep us on the safe
  side, any other characters -- including also byte components of
  UTF-8-encoded non-ASCII characters -- should appear *only in their
  percent-encoded form*; and the `,` character *cannot be included at
  all*, even in its percent-encoded form!)

Multiple *values* of a query parameter can be specified by separating
them with `,` (bare or percent-encoded) or, alternatively, just by
repeating the parameter with different *values*.

!!! warning "Caution"

    The `time.min` parameter is mandatory for every query. A query without
    it will result in a redirection (a HTTP response with status code 307)
    to a URI containing the query with that parameter added.

#### Example URIs (with Queries)

```
https://n6api.cert.pl/report/inside.json?ip=198.51.100.234&modified.min=2024-02-12T00:00:00Z&time.min=2024-02-01T00:00:00Z
https://n6api.cert.pl/report/inside.json?name=%27%25xxx%27%3D&time.min=2024-02-01T01:01:01Z
https://n6api.cert.pl/report/inside.sjson?name=malware1,malware2&time.min=2024-02-01T01:02:03Z
https://n6api.cert.pl/report/inside.csv?name=malware1&name=malware2&time.min=2024-02-01T04:05:06Z
https://n6api.cert.pl/report/threats.json?time.min=2024-02-01T07:58:59Z
```


### Response

*n6 REST API* uses standard HTTP status codes: **200** (success),
**307** (redirection), **400** (incorrect *query*), **401** (auth
required), **403** (no permission), **404** (incorrect *resource*
or *format*), **500** (server error).

In case of an immediate error, a response containing a text description
of the error is returned, with a suitable HTTP status code. However, if
an error occurs when some part of the proper (non-error) response body
has already been emitted (using [chunked transfer
encoding](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Transfer-Encoding#chunked_encoding)...),
the emission of the response is just discontinued.

The content of a proper response body depends on the requested *format*
(see the [previous section](#request)). For `json`, it is a single
*array* (in the [JSON](https://www.json.org/json-en.html) format) whose
elements are *objects*, each of which represents a single *event*. Those
objects' possible attributes (keys) are described in the [*Event
Attributes*](#event-attributes) section below.

If you expect large responses, we recommend using a "streamed" variant
of `json`: the `sjson` format -- where the response consists of
concatenated top-level objects delimited by newlines (line feed, i.e.,
ASCII 0x0A). Each top-level object is represented in a single line (no
pretty-print), which allows to parse results incrementally. Otherwise
this format is identical with plain `json`.

Retrieved events are always sorted by their `time`, descendingly.

#### Example Response Body

(assuming `json` as requested *format*)

```json
[
{
    "id": "392ab73bbe7bcd6a56c84af2234987a4",
    "source": "hidden.42",
    "restriction": "need-to-know",
    "confidence": "medium",
    "category": "bots",
    "modified": "2023-05-04T11:45:27Z",
    "time": "2024-05-04T10:59:03Z",
    "address": [
        {
            "ip": "203.0.113.42",
            "cc": "PL",
            "asn": 1234
        },
        {
            "ip": "203.0.113.123",
            "cc": "PL",
            "asn": 1234
        }
    ],
    "adip": "x.x.51.198",
    "dport": 22,
    "name": "avalanche-andromeda",
    "origin": "sinkhole",
    "proto": "tcp",
    "sport": 58362
},
{
    "id": "eb450876ab458d05238ffe523e56d9b5",
    "source": "hidden.123",
    "restriction": "public",
    "confidence": "low",
    "category": "phish",
    "modified": "2024-05-04T13:18:43Z",
    "time": "2024-05-03T01:57:26Z",
    "address": [
        {
            "ip": "192.0.2.7",
            "cc": "GB",
            "asn": 543210
        }
    ],
    "expires": "2024-05-05T01:57:26Z",
    "status": "active",
    "fqdn": "1234567890qwerty.example.com",
    "target": "Example.com Inc.",
    "url": "http://1234567890qwerty.example.com/click.me"
}
]
```


## Attributes and Parameters (Reference)

All *event attributes* and *query parameters* supported by the current
version of *n6* are listed in the following sections – except that in
this document we do *not* cover any attributes/parameters that are
visible/available *only* for *privileged* users [*technically: those
users whose organizations have the `full_access` flag set to `True` in
the n6's Auth DB*].


### Event Attributes

Below, the attributes (keys) which are always present are marked as
**[mandatory]**; the rest are optional. The types of attribute values
are noted in round brackets.

- `action` (*string*) Action taken by malware (e.g., `"redirect"`,
  `"screen grab"`).
- `address` (*array of objects*) IP addresses related to the threat. For
  malicious websites -- `A` records in DNS; for connections to sinkhole
  and scanning hosts -- source IP addresses. Attributes of child objects:
    - `ip` (*string*) **[mandatory]** IPv4 address in dot-decimal notation.
    - `cc` (*string*) Country code ([ISO
      3166-1](https://www.iso.org/iso-3166-country-codes.html) *alpha-2*).
    - `asn` (*integer*) Autonomous system number (without "AS" prefix).
- `adip` (*string*) Anonymized destination IP address in dot-decimal
  notation, with some octets replaced with `x`. The attribute does not
  apply to addresses of malicious websites.
- `block` (*boolean*) Whether the domain has been blocked (see also:
  `fqdn`, `url`).
- `category` (*string*) **[mandatory]** Category of the event. Possible values:
    - `"amplifier"`: hosts that can be used in amplification attacks (DoS)
    - `"bots"`: infected machines
    - `"backdoor"`: addresses of web shells or other types of backdoors installed on compromised servers
    - `"cnc"`: botnet controllers
    - `"deface"`: hosts with website defacement
    - `"dns-query"`: DNS queries and answers (no determination on legitimacy/maliciousness)
    - `"dos-attacker"`: (distributed) denial-of-service attacks -- details related to sources
    - `"dos-victim"`: (distributed) denial-of-service attacks -- details related to victims
    - `"flow"`: network traffic in layer 3 (no determination on legitimacy/maliciousness)
    - `"flow-anomaly"`: anomalous network activity (not necessarily malicious)
    - `"fraud"`: activities and entities related to financial fraud
    - `"leak"`: leaked credentials or personal data
    - `"malurl"`: malicious URLs (details about web servers infecting users)
    - `"malware-action"`: actions that malware is configured to make on infected machines
    - `"phish"`: phishing campaigns (similar to malurl)
    - `"proxy"`: open proxy servers
    - `"sandbox-url"`: URLs contacted by malware
    - `"scam"`: URLs used for scam
    - `"scanning"`: hosts performing port scanning
    - `"server-exploit"`: attackers actively attempting to exploit servers
    - `"spam"`: hosts sending spam
    - `"spam-url"`: addresses found in spam
    - `"tor"`: Tor network exit nodes
    - `"vulnerable"`: addresses of vulnerable devices or services
    - `"webinject"`: injects used by banking trojans
    - `"other"`: other activities not included above
- `confidence` (*string*) **[mandatory]** Level of trust that the
  information is accurate. Possible values: `"low"`, `"medium"`,
  `"high"`.
- `dip` (*string*) Destination IP address (e.g., of a sinkhole or
  honeypot) in dot-decimal notation. The attribute does not apply to
  addresses of malicious websites. *Note:* for most data sources, to
  convey destination IP information, the `adip` attribute (see above)
  is used instead of `dip`.
- `dport` (*integer*) Destination port used for TCP or UDP communication.
- `email` (*string*) E-mail address associated with the threat (e.g.,
  source of spam, victim of a data leak).
- `expires` (*string*) Time until which the blacklist entry
  is considered valid (usually 48h from the time of the latest
  update that included the entry), formatted in an [RFC
  3339](https://datatracker.ietf.org/doc/html/rfc3339)-compliant way.
- `fqdn` (*string*) Fully qualified domain name related to the threat.
  For malicious websites -- the URL's domain; for bots and scanners --
  the destination domain.
- `iban` (*string*) International Bank Account Number associated with
  fraudulent activity.
- `id` (*string*) **[mandatory]** System-wide unique identifier of the
  event.
- `injects` (*array of objects*) Collection of objects describing a set
  of injects performed by banking trojans when a user loads a targeted
  website (see `url_pattern`). Structure of objects depends on malware
  family (not specified here).
- `md5` (*string*) MD5 hash (hexadecimal) of the binary file related to
  the event.
- `modified` (*string*) **[mandatory]** Time when the event was made
  available through the API (i.e., when the record was inserted into the
  *n6*'s Event DB) or was last updated (which may apply to blacklist
  entries and aggregated events...); formatted in an [RFC
  3339](https://datatracker.ietf.org/doc/html/rfc3339)-compliant way.
- `name` (*string*) Category-dependent name of the threat (e.g.,
  `"virut"`, `"SSH Scan"`).
- `origin` (*string*) Method used to obtain the data. Possible values:
    - `"c2"`: direct botnet controller observation
    - `"dropzone"`: botnet dropzone observation
    - `"proxy"`: monitoring traffic on a proxy server
    - `"p2p-crawler"`: active crawl of a peer-to-peer botnet
    - `"p2p-drone"`: passive listening to traffic in a peer-to-peer botnet
    - `"sinkhole"`: data obtained from sinkhole
    - `"sandbox"`: results from behavioral analysis
    - `"honeypot"`: interaction with honeypots, both client and server-side
    - `"darknet"`: monitoring of traffic collected by darknet
    - `"av"`: reports from antivirus systems
    - `"ids"`: reports from intrusion detection and prevention systems
    - `"waf"`: reports from web application firewalls
- `phone` (*string*) Telephone number (national or international) related
  to the event. Typically consists of decimal digits; optionally prefixed
  by the plus symbol.
- `product` (data-source-dependent type, usually *string*) Vulnerable
  software product information: its actual or abbreviated name, and/or
  version, and/or other data (exact shape of the information depends on
  data source).
- `proto` (*string*) Protocol used on top of the network layer. Possible
  values: `"tcp"`, `"udp"`, `"icmp"`.
- `registrar` (*string*) Name of the domain registrar (see also: `fqdn`).
- `replaces` (*string*) Identifier (`id`) of the event that was
  superseded by the current one. Specific to blacklists (see also: `status`).
- `restriction` (*string*) **[mandatory]** Classification level.
  Possible values: `"internal"`, `"need-to-know"`, `"public"`.
- `sha1` (*string*) SHA-1 hash (hexadecimal) of the binary file related
  to the event.
- `sha256` (*string*) SHA-256 hash (hexadecimal) of the binary file
  related to the event.
- `source` (*string*) **[mandatory]** Unique identifier of the source
  (producer) of the event (*note:* in the *n6*'s documentation and code we
  often refer to this piece of information using the term *data source*,
  or just *source*). The value always consists of two dot-separated parts:
  the *source provider* label (identifying a group of data sources that
  are, typically, provided by a certain organization or person) and the
  *source channel* label (identifying a specific data feed); both parts
  may be anonymized for non-privileged users (depending on the configuration
  in the *n6*'s Auth DB).
- `sport` (*integer*) Source port used in TCP or UDP communication.
- `status` (*string*) Blacklist entry status. Possible values:
    - `"active"`: item is currently in the list
    - `"delisted"`: item has been removed from the list (marked as inactive)
      by the data source
    - `"expired"`: item is considered no longer active, even though it might
      still be present in the list last published by the data source
    - `"replaced"`: some characteristics of the entry (e.g., IP address)
      have changed, so now the entry is represented by another event (see
      above: `replaces`)
- `target` (*string*) Organization or brand that is the target of the
  attack (applicable to phishing).
- `time` (*string*) **[mandatory]** Time of event occurrence (i.e., in the
  general case, *not* the time of reporting), formatted in an [RFC
  3339](https://datatracker.ietf.org/doc/html/rfc3339)-compliant way.
- `url` (*string*) URL related to the event (*note:* formally, it is a
  *URI* or *IRI*, according to the respective definition in [RFC
  3986](https://datatracker.ietf.org/doc/html/rfc3986) or [RFC
  3987](https://datatracker.ietf.org/doc/html/rfc3987)).
- `url_pattern` (*string*) Wildcard pattern or regular expression
  triggering injects, used by banking trojans.
- `username` (*string*) Local identifier (login) of the affected user.
- `x509fp_sha1` (*string*) SHA-1 fingerprint (hexadecimal) of an
  SSL/X.509 certificate.
- `x509issuer` (*string*) Issuer of an SSL/X.509 certificate.
- `x509subject` (*string*) Subject of an SSL/X.509 certificate.


### Query Parameters

Many of the event attribute names listed in the [previous section](#event-attributes)
are also valid names of query parameters. Those parameters are:

- `category`
- `confidence`
- `dport`
- `fqdn`
- `id`
- `md5`
- `name`
- `origin`
- `proto`
- `replaces`
- `sha1`
- `sha256`
- `source`
- `sport`
- `status`
- `target`
- `url`

Each of those parameters, if specified, narrows search results to events
which have the corresponding attribute set to a value matching the
specified parameter value (or, if multiple values of the parameter are
specified, matching *any* of them).

Similarly, these are query parameters which correspond to component
fields of the `address` attribute:

- `ip`
- `cc`
- `asn`

Additionally, the following query parameters can be used to specify
wider search criteria:

- `ip.net` -- IPv4 network in CIDR notation, e.g. `203.0.113.0/24`
  (referring to `ip` values in events' `address`).
- `fqdn.sub` -- substring of events' `fqdn`.
- `url.sub` -- substring of events' `url`.

A special class of query parameters are those specifying *time ranges*.
The name of each of those parameters consists of two parts:

- the first part determines which time-related attribute(s) is/are to
  be tested (see below);
- the second part is one of:
    - `.min` -- meaning that the parameter specifies a minimum value (i.e.,
      that matching attribute values are *greater than or equal to* the
      parameter value).
    - `.max` -- meaning that the parameter specifies a maximum value (i.e.,
      that matching attribute values are *less than or equal to* the parameter
      value).
    - `.until` -- like `.max`, but *excluding* the parameter value from the
      time range being specified (which means that matching attribute values
      are *less than* the parameter value).

Those special parameters are:

- `time.min` **[mandatory]**, `time.max`, `time.until` -- referring to
  events' `time`.
- `modified.min`, `modified.max`, `modified.until` -- referring to
  events' `modified`.
- `active.min`, `active.max`, `active.until` -- referring to the
  `expires` attribute if an event has it (which applies to blacklist
  entries), and otherwise to the `time` attribute.

Each of those parameters, if present, should be set to a time in an [RFC
3339](https://datatracker.ietf.org/doc/html/rfc3339)-compliant format
(using only the upper-case form of the letters `T`/`Z`, if any of them
is present) -- except that the UTC offset part can be omitted (then just
`+00:00` is assumed).

A few examples:

- `time.min=2023-10-25T00:00:00Z` would select events with `time` set
  to midnight on October 25, 2023 (UTC), or to any later time;
- `time.min=2024-09-04T18:46:42&time.max=2024-09-04T19:59:01` would
  select events with `time` set to any times from 6:46 p.m. and 42
  seconds to 7:59 p.m. and 1 second, on September 4, 2024 (UTC) --
  *including* that upper limit (i.e., the specified interval is a
  *right-closed* one);
- `time.min=2024-09-04T18:46:42&time.until=2024-09-04T19:59:01` would
  select events with `time` set to any times from 6:46 p.m. and 42
  seconds to 7:59 p.m. and 1 second, on September 4, 2024 (UTC) --
  *excluding* that upper limit (i.e., the specified interval is a
  *right-open* one).

!!! note

    `time.min` is the only query parameter that is *mandatory*.

Apart from all that, global *query options* can be specified using the
following parameters:

- `opt.limit` (integer) -- maximum number of events to be retrieved
  (as noted earlier, events are always sorted by their `time`,
  descendingly). *Note:* by default, no limit is imposed.
- `opt.primary` (Boolean flag: `true` or `false`; default value:
  `false`) -- set it to `true` to restrict the content of retrieved
  events to *primary data* (the original data from data sources), i.e.,
  to hide event attributes (or their child objects' items) whose values
  were determined/inferred by the *n6* system itself (e.g., by performing
  DNS/GeoIP queries).

When it comes to the special *time range* and *query option* parameters
described above, each of them can have at most one value (i.e., *no
multiple values* of a parameter are allowed).


### Summary Table

| Event Attribute                  | Attribute Type      | Attribute Restrictions | Corresponding Query Parameter(s)    | Parameter Restrictions             |
|----------------------------------|---------------------|------------------------|-------------------------------------|------------------------------------|
| `action`                         | *string*            |                        | –                                   |                                    |
| `address`                        | *array of objects*  |                        | `ip`                                |                                    |
|                                  |                     |                        | `ip.net`                            |                                    |
|                                  |                     |                        | `cc`                                |                                    |
|                                  |                     |                        | `asn`                               |                                    |
| `adip`                           | *string*            |                        | –                                   |                                    |
| `block`                          | *boolean*           |                        | –                                   |                                    |
| `category`                       | *string* (enum)     | mandatory              | `category`                          |                                    |
| `confidence`                     | *string* (enum)     | mandatory              | `confidence`                        |                                    |
| `dip`                            | *string*            |                        | –                                   |                                    |
| `dport`                          | *integer*           |                        | `dport`                             |                                    |
| `email`                          | *string*            |                        | –                                   |                                    |
| `expires`                        | *string* (time)     | bl-entries-only        | (see: `active.*` params below)      |                                    |
| `fqdn`                           | *string*            |                        | `fqdn`                              |                                    |
|                                  |                     |                        | `fqdn.sub`                          |                                    |
| `iban`                           | *string*            |                        | –                                   |                                    |
| `id`                             | *string*            | mandatory              | `id`                                |                                    |
| `injects`                        | *array of objects*  |                        | –                                   |                                    |
| `md5`                            | *string*            |                        | `md5`                               |                                    |
| `modified`                       | *string* (time)     | mandatory              | `modified.min`                      | no&nbsp;multiple values            |
|                                  |                     |                        | `modified.max`                      | no&nbsp;multiple values            |
|                                  |                     |                        | `modified.until`                    | no&nbsp;multiple values            |
| `name`                           | *string*            |                        | `name`                              |                                    |
| `origin`                         | *string* (enum)     |                        | `origin`                            |                                    |
| `phone`                          | *string*            |                        | –                                   |                                    |
| `product`                        | *string*/another... |                        | –                                   |                                    |
| `proto`                          | *string* (enum)     |                        | `proto`                             |                                    |
| `registrar`                      | *string*            |                        | –                                   |                                    |
| `replaces`                       | *string*            | bl-entries-only        | `replaces`                          |                                    |
| `restriction`                    | *string* (enum)     | mandatory              | –                                   |                                    |
| `sha1`                           | *string*            |                        | `sha1`                              |                                    |
| `sha256`                         | *string*            |                        | `sha256`                            |                                    |
| `source`                         | *string*            | mandatory              | `source`                            |                                    |
| `sport`                          | *integer*           |                        | `sport`                             |                                    |
| `status`                         | *string* (enum)     | bl-entries-only        | `status`                            |                                    |
| `target`                         | *string*            |                        | `target`                            |                                    |
| `time`                           | *string* (time)     | mandatory              | `time.min`                          | mandatory, no&nbsp;multiple values |
|                                  |                     |                        | `time.max`                          | no&nbsp;multiple values            |
|                                  |                     |                        | `time.until`                        | no&nbsp;multiple values            |
|                                  |                     |                        | (see also: `active.*` params below) |                                    |
| `url`                            | *string*            |                        | `url`                               |                                    |
|                                  |                     |                        | `url.sub`                           |                                    |
| `url_pattern`                    | *string*            |                        | –                                   |                                    |
| `username`                       | *string*            |                        | –                                   |                                    |
| `x509fp_sha1`                    | *string*            |                        | –                                   |                                    |
| `x509issuer`                     | *string*            |                        | –                                   |                                    |
| `x509subject`                    | *string*            |                        | –                                   |                                    |
| (`expires`/`time`, see above...) |                     |                        | `active.min`                        | no&nbsp;multiple values            |
|                                  |                     |                        | `active.max`                        | no&nbsp;multiple values            |
|                                  |                     |                        | `active.until`                      | no&nbsp;multiple values            |
| –                                |                     |                        | `opt.limit`                         | no&nbsp;multiple values            |
| –                                |                     |                        | `opt.primary`                       | no&nbsp;multiple values            |


## API Changelog

### **4.12.0** – 2024-XX-XX

After this release of *n6*, any changes to *n6 REST API* will be
recorded in this section (in addition to being included in the main
[Changelog](../changelog.md)).

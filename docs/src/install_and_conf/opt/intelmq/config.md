# Installation and Configuration

## Necessary _n6_ packages

Make sure you have the `N6DataPipeline` package installed:

```bash
(env)$ ./do_setup.py N6DataPipeline
```

## _IntelMQ_ package

Install the `intelmq` package from PyPI. For the best compatibility,
install the `3.0.2` version, which is the last version tested.

```bash
(env)$ pip install intelmq
(env)$ useradd -d /opt/intelmq -U -s /bin/bash intelmq
$ sudo intelmqsetup
```

## _IntelMQ_ runtime configuration

n6 bot runner uses _IntelMQ_'s runtime configuration. It may be placed
in '/opt/intelmq/etc/runtime.yaml' or '/etc/intelmq/runtime.yaml' etc.

This YAML config's options are the IDs of the bots. These IDs will be used as arguments for
the n6 command `n6run_bot`. You can use existing bot configurations or define new ones.

n6 system for running _IntelMQ_ bots reads the `n6config` subsection in bot ID section, which is ignored
by the _IntelMQ_. This subsection provides some configuration, which may be required for some types
of bots (like parser bots).

### Example _IntelMQ_ bot configuration

```yaml
spamhaus-drop-parser:
  bot_id: spamhaus-drop-parser
  description:
    Spamhaus Drop Parser is the bot responsible to parse the DROP, EDROP,
    DROPv6, and ASN-DROP reports and sanitize the information.
  enabled: false
  group: Parser
  groupname: parsers
  module: intelmq.bots.parsers.spamhaus.parser_drop
  name: Spamhaus Drop
  parameters:
    destination_queues:
      _default: [taxonomy-expert-queue]
  run_mode: continuous
  n6config:
    default_binding_key: spamhaus.intelmq-collector
```

The section defines the bot with ID `spamhaus-drop-parser`, which is a parser bot. Parser bots
require a `default_binding_key` option in the `n6config` section. The option's value means
that the parser will accept incoming messages from the collector, which sends messages with
routing key `spamhaus.intelmq-collector`.

## _n6_ pipeline configuration

You have to place _IntelMQ_ components somewhere in the pipeline. It can be achieved by configuring
components that will be used in the n6 config's `pipeline` section. For example: you want to
obtain the following order of components:

```
spamhaus.intelmq-collector -> spamhaus-drop-parser -> maxmind-expert
-> gethostbyname-1-expert -> intelmq-to-n6-adapter -> enricher
```

The `intelmq-to-n6-adapter` is a component, which converts messages from _IntelMQ_ format to
n6 format.

The `pipeline` configuration should look like:

```ini
[pipeline]
enricher = parsed, intelmq-to-n6-adapter
intelmq-to-n6-adapter = gethostbyname-1-expert
gethostbyname-1-expert = maxmind-expert
maxmind-expert = intelmq-parsed
```

`intelmq-parsed` is a default routing state (part of routing key that messages are sent with,
characteristic for the component) for the parser bots. Routing states of expert bots are by
default their IDs.

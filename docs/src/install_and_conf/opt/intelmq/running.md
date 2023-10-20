# Running _IntelMQ_ Bots and Message Format Adapters

## Running a bot

```bash
(env)$ n6run_bot [-h] [-e] BOT_ID
```

Arguments:

- **BOT_ID** ID of the bot to run, which is defined in the _IntelMQ_ runtime config
- **-h, --help** show help message
- **-e, --exception-proof** Run the bot in the "exception-proof" mode, where it will send
  forward incoming messages, even if an exception is raised

## Running message format adapters

### _n6_ to _IntelMQ_ message format adapter

```bash
(env)$ n6run_adapter_to_intelmq
```

### _IntelMQ_ to _n6_ message format adapter

```bash
(env)$ n6run_adapter_to_intelmq
```

# Running IntelMQ bots and message format adapters

## Running a bot

```bash
(env)$ n6run_bot [-h] [-e] BOT_ID
```

Arguments:
* **BOT_ID** ID of the bot to run, which is defined in the IntelMQ runtime config
* **-h, --help** show help message
* **-e, --exception-proof** Run the bot in the "exception-proof" mode, where it will send
forward incoming messages, even if an exception is raised

## Running message format adapters

### n6 to IntelMQ message format adapter
```bash
(env)$ n6run_adapter_to_intelmq
```

### IntelMQ to n6 message format adapter
```bash
(env)$ n6run_adapter_to_intelmq
```

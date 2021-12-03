# Examining Data Flow

To examine the *n6* data flow
(see: [n6 Architecture and Data Flow Overview](../../data_flow_overview.md))
you can do the following:

* Run some collector to check data flow.

```bash
(env)$ n6collector_spam404
```

!!! tip

    You may want, firstly, to temporarily terminate the corresponding parser
    (by the command `stop <process>` if [Supervisor](supervisor.md) is in
    use) -- to be able to see (in the RabbitMQ web management panel)
    incoming messages on the parser's input queue (before they are consumed
    by the parser).

* Log into the RabbitMQ web management panel to check message queues.
* Log into the *n6* Portal and query the *n6* API through the search form.
* Query the *n6* REST API (you can use *curl*, a web browser, etc.).

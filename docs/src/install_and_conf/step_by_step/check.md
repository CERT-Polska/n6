Now we can go through the workflow (see [n6 Architecture and Data Flow Overview](/data_flow_overview/))

This will be step-by-step go through data flow. You can use [Supervisor](supervisor.md) for managing the `n6 pipeline`.
For our examples we will use source `cert-pl.shield`.

## Initializing the queues

Each component of `n6 datapipeline` besides `n6collector` initializes (if it's not existing already) and consumes queue in the broker. So for example running `n6collector_certplshield` won't create any queue. We need to first initialize it with `n6parser_certplshield`. Then push the messages by running `n6collector_certplshield`. Finally we can *consume* the messages by running `n6parser_certplshield`. However to push the messages further we need to run the next component `n6aggregator`/`n6enrich` to have the neccessary queue.

So first things first let's initialize needed queues.
To do this just call appropariate commands (after a few seconds you might terminate them for now with `CTRL+C`):

```bash
(env_py3k)$ n6parser_certplshield
(env_py3k)$ n6enrich
(env_py3k)$ n6filter
(env_py3k)$ n6recorder
```

To check if the queues were initilized go to `https://localhost:15671` and log in, you should see that there are appropariate queues.

Now it is time to go through the workflow by first calling the `cert-pl.shield` collector:

```bash
(env_py3k)$ n6collector_certplshield
```

And after a few seconds there should be messages on the `cert-pl.shield` queue.

You can push them further by again calling next steps of the data flow:
`n6parser_certplshield` -> `n6enrich` -> `n6filter` -> `n6recorder`->`Database`.
By doing it step-by-step you can see what happens to the messages at each phase of the data handling process.

!!!Note
    The `n6comparator` is not used in this example as `cert-pl.shield` is not a black list source.

Now if the messages are in database you can log in to the *n6 portal* and:

- go to **All Incidents** page.
- click the **events** tab.
- press **search** button (you can also set start date on datepicker).

and Events will load. If you used different collectors you can also add filters to search for specific events. To see more detailed information on how n6 stores the data, you might want to connect to MariaDB database via terminal or GUI client.

You can also check the data in REST API, but to do so you need to set your `API KEY`.
To set your `API KEY` follow these steps:

- Click the user icon located in the top right corner.
- Go to user settings.
- Under multi-factor authentication you will see `API KEY` section.
- Click **generate key**.
- Now you can click on the generated key to copy it to clickboard.

Then you can make a request to the REST API. To obtain the collected
data (if any) for the current user, do:


```bash
curl -k 'https://localhost:4443/search/events.json?time.min=2015-01-01T00:00:00' -H "Authorization: Bearer YOUR_API_KEY"
```

 And you should see data in the JSON format:

```json
{
    "modified": "2024-01-01T10:10:10Z",
    "category": "phish",
    "fqdn": "www.example-fqdn-1.pl",
    "time": "2020-01-01T01:01:01Z",
    "id": "d652d5ad-05e0-4aee-a7b5-48f7b60e1509",
    "confidence": "low",
    "source": "source-provider.source-channel",
    "restriction": "public"
},
{
    "modified": "2024-01-01T10:10:10Z",
    "category": "phish",
    "fqdn": "www.example-fqdn-2.pl",
    "time": "2020-02-02T01:01:01Z",
    "id": "ca2939bf-b535-4fa0-89da-4bf344f08b72",
    "confidence": "low",
    "source": "source-provider.source-channel",
    "restriction": "public"
},
{
    "modified": "2024-01-01T10:10:10Z",
    "category": "phish",
    "fqdn": "www.example-fqdn-2.pl",
    "time": "2020-03-03T01:01:01Z",
    "id": "ba5fa70d-70b4-4b35-a505-7073427d407b",
    "confidence": "low",
    "source": "source-provider.source-channel",
    "restriction": "public"
},
{
    "modified": "2024-01-01T10:10:10Z",
    "category": "phish",
    "fqdn": "www.example-fqdn-3.pl",
    "time": "2020-04-04T01:01:01Z",
    "id": "cbe2d073-5e25-4baa-87ae-07bc35bb2be3",
    "confidence": "low",
    "source": "source-provider.source-channel",
    "restriction": "public"
},
{
    "modified": "2024-01-01T10:10:10Z",
    "category": "phish",
    "fqdn": "www.example-fqdn-4.pl",
    "time": "2020-05-05T01:01:01Z",
    "id": "9c3929f4-8991-4cd7-81ff-bf9dff642f65",
    "confidence": "low",
    "address": [
        {
            "ip": "111.111.111.111"
        }
    ],
    "source": "source-provider.source-channel",
    "restriction": "public"
},
{
    "modified": "2024-01-01T10:10:10Z",
    "category": "phish",
    "fqdn": "www.example-fqdn-5.pl",
    "time": "2020-06-06T01:01:01Z",
    "id": "aafe6237-cdb9-4c88-9995-c5c40c15f07c",
    "confidence": "low",
    "address": [
        {
            "ip": "222.222.222.222"
        }
    ],
    "source": "source-provider.source-channel",
    "restriction": "public"
}
```
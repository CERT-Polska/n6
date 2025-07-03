<style>
  code.language-bash::before{
    content: "$ ";
  }
</style>


# Trying It Out

This will be a step-by-step go through the *n6* data flow (see:
*[Architecture and Data Flow Overview](../../data_flow_overview.md)*).

For our examples we will use the `cert-pl.shield` *data source*.

!!! tip

    For the purposes of this guide, according to the assumed logging
    configuration (see the relevant fragments of the previous chapter
    [*Configuring* n6 *Components*](config.md)), all *n6* components
    put their log entries into the `/home/dataman/logs/log_n6_all`
    file (you can observe its content, e.g., with the `tail -f
    /home/dataman/logs/log_n6_all` command run in a concurrent shell
    session...).


## Where Are We?

Again, before any operations, ensure the current working directory is
the home directory of `dataman` (which is supposed to be the user in
whose shell you execute all commands):

```bash
cd ~
```

Also, make sure the Python *virtual environment* in which *n6* [has been
installed](installation.md#actual-installation) is active:

```bash
source ./env_py3k/bin/activate
```


## Initializing the queues

To check that no *n6 pipeline*'s RabbitMQ queues exist yet, visit the broker's
web interface [https://localhost:15671](https://localhost:15671) (log in using
the credentials: user `guest`, password `guest`).

Note that the `n6collector_certplshield` collector (we are about to
use), if it was started right now, would *not* create by itself any
RabbitMQ queue for the collector's output!

Most kinds of *n6 pipeline* components -- but *not* `n6collector_*` ones
-- **declare** their _**input**_ queues (*declaration* causes *creation*
if the queue did not exist yet) and **subscribe** to them.

So, first things first, initialize the necessary queues by executing the
following commands... Each of them, after a few seconds, should be (for
now), terminated with `Ctrl+C`. Thanks to the broker's web interface you
can observe the creation of consecutive queues...

```bash
n6parser_certplshield202505    # ...and Ctrl+C after several seconds
```

```bash
n6enrich     # ...and Ctrl+C after several seconds
```

```bash
n6filter     # ...and Ctrl+C after several seconds
```

```bash
n6recorder   # ...and Ctrl+C after several seconds
```

!!! note

    The `n6aggregator` conponent is not used here because our
    `cert-pl.shield` source is not a *high-frequency* (*hifreq*) one.

    The `n6comparator` conponent is not used here because our
    `cert-pl.shield` source is not a *blacklist* (*bl*) one.


## *n6 Pipeline* in Action

Now, let some data enter the pipeline -- thanks to running the
`cert-pl.shield` collector:

```bash
n6collector_certplshield
```

And after a few seconds there should be some messages in the input queue
of the `n6parser_certplshield202505` parser.

You can push the data further, along the pipeline, by consecutively
running again each of the previously run components
(`n6parser_certplshield202505` → `n6enrich` → `n6filter` →
`n6recorder`; the last one inserts ready *events* into our *Event DB*):

```bash
n6parser_certplshield202505 &
```

```bash
n6enrich &
```

```bash
n6filter &
```

```bash
n6recorder &
```

By doing that step-by-step you can see, thanks to the broker's web
interface, what happens to the messages at each phase of the data
handling process.

When you decide that it is enough, execute the command:

```bash
pkill -e --signal SIGINT 'n6(parser|enrich|filter|recorder)'
```

!!! tip

    Of course, starting and stopping *n6 pipeline* components by hand
    is tedious, considering their number (all those *collectors* and
    *parsers*...), especially that -- as you just saw -- most of the
    components are *daemon*-style ones (nearly all, besides *collectors*).

    Employing some tool to manage that stuff is, therefore, highly
    recommended. One such tool is *Supervisor* -- discussed in a separate
    chapter: [*Managing* n6 Pipeline *Components with*
    Supervisor](supervisor.md).


## Using *n6 Portal* (selected examples)

Now that some *events* are in the database, it is time to make use of
*n6 Portal*!

### First Time on *n6 Portal*

In a web browser, go to the *n6 Portal*'s log-in page:
[https://localhost/](https://localhost/) -- and enter the credentials:

* **Login:** `login@example.com`
* **Password:** *the password you entered interactively [when the
  **`n6populate_auth_db`** script was being executed](config.md#auth-db)*

Now you will be asked to configure your second factor authentication (on
your phone or another device). **Follow the displayed instructions.**

### Querying *Event DB*

* You are on the **All Incidents** page.
* Click the **Global search** tab.
* Press the **Search** button.

...and *events* will be searched.

!!! tip

    If no events are found, try changing the *start date* to some earlier
    one...

!!! info

    You can also add filters (with the **Add filter** button) to make your
    search more specific...

### Generating API Key

You can also query the *Event DB* via *n6 REST API*, but first you need
to generate (via *n6 Portal*) your *API key*:

* Click the user icon located in the top right corner.
* Go to **User Settings**.
* Below the *Multi-factor authentication* section you will see the **API
  key** section.
* Click **Generate key**.
* Now you can click on the generated key to copy it to clipboard.


## Querying *Event DB* via *n6 REST API*

Now you can make a request to the REST API. To obtain the collected
data (if any) for the current user, execute (replacing `YOUR_API_KEY`
with your actual **API key** you just generated):

```bash
curl --insecure \
    'https://localhost:4443/search/events.json?time.min=2015-01-01T00:00:00&opt.limit=5' \
    -H 'Authorization: Bearer YOUR_API_KEY'
```

The output should be *event* data in the JSON format, for example:

```json
[
{
    "time": "2025-01-20T09:48:04Z",
    "restriction": "public",
    "confidence": "high",
    "id": "ac40da5f2426e5508d82ce1d9e6c0671",
    "source": "hidden.2654ce176e42df70",
    "modified": "2025-07-03T00:32:53Z",
    "fqdn": "bad-site.example.com",
    "category": "phish"
},
{
    "time": "2025-01-20T09:48:04Z",
    "restriction": "public",
    "confidence": "high",
    "id": "b5bdb192fdedd791c5aa23e16ed2975e",
    "source": "hidden.2654ce176e42df70",
    "modified": "2025-07-03T00:32:54Z",
    "fqdn": "nasty-site.example.net",
    "category": "phish"
},
{
    "time": "2025-01-20T09:48:03Z",
    "restriction": "public",
    "confidence": "high",
    "id": "933aeb204d3bf778adbcaaf4e983dbf3",
    "source": "hidden.2654ce176e42df70",
    "modified": "2025-07-03T00:32:53Z",
    "fqdn": "what.example.org",
    "category": "phish"
},
{
    "time": "2025-01-20T09:47:04Z",
    "restriction": "public",
    "confidence": "high",
    "id": "ab68ceb7978ac7ae9559d68afadb73de",
    "source": "hidden.2654ce176e42df70",
    "modified": "2025-07-03T00:32:52Z",
    "fqdn": "something.example.com",
    "category": "phish"
},
{
    "time": "2025-01-20T09:47:03Z",
    "restriction": "public",
    "confidence": "high",
    "id": "1b9516eff4f0ac8b8be09a2868d33dfd",
    "source": "hidden.2654ce176e42df70",
    "modified": "2025-07-03T00:32:52Z",
    "fqdn": "sth.example.info",
    "category": "phish"
}
]
```


## Managing *Auth DB* Content with *n6 Admin Panel*

The *n6 Admin Panel*'s user interface is straightforward, as it provides
mainly
[CRUD](https://en.wikipedia.org/wiki/Create,_read,_update_and_delete)-like
operations...

Just go to [https://localhost:4444/](https://localhost:4444/) in a web
browser and experiment.

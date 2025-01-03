<style>
  code.language-bash::before{
    content: "$ ";
  }
</style>
# Docker-Based Installation

## Opening remarks

This short guide describes how to run, for testing and exploration, the
latest version of *n6* -- using the _Docker_ and _docker compose_ tools.

The goal of this guide is to give you an example of how you can run *n6*
in the easiest possible way, so that you can learn -- by monitoring and
experimenting -- how the *n6* system works and how you can interact with
it. Keep in mind that this guide was designed for Linux-based systems.
Even with usage of _Docker_ and _docker compose_, we cannot guarantee
that it will work on other systems (such as Windows or Mac OS).


!!! warning "Disclaimer: what these materials _are_ and what they are _not_"

    This installation guide, as well as the stuff you can find in the
    [`etc/`](https://github.com/CERT-Polska/n6/tree/master/etc) and
    [`docker/`](https://github.com/CERT-Polska/n6/tree/master/docker)
    directories of the *n6* source code repository, concern setting up an
    *n6* instance just for testing, exploration and experimentation, i.e.,
    **not for production** (at least, *not* without careful security-focused
    adjustments).

    In other words, these materials are *not* intended to be used as a
    recipe for a secure production setup -- in particular, when it comes to
    (but not limited to) such issues as X.509 certificates (note that those
    in the [`etc/ssl/*`](https://github.com/CERT-Polska/n6/tree/master/etc/ssl)
    directories of the source code repository are purely example ones --
    they should *never* be used for anything related to production
    systems!), authentication and authorization settings (which in these
    materials are, generally, either skipped or reduced to what is necessary
    just to run the stuff), or file access permissions.

    It should be obvious that an experienced system administrator and/or
    security specialist should prepare and/or carefully review and adjust
    any configuration/installation/deployment of services that are to be
    made production ones, in particular if those services are to be made
    public.

## Requirements

- _Docker Engine_ installed (a reasonably new version)
- _Docker Compose_ installed (a reasonably new version)
- The *n6* [source code repository](https://github.com/CERT-Polska/n6) cloned


## Building the environment

!!! note

    Make sure you are in the top-level directory of the cloned source code repository.

To build our demonstrational *n6* environment we use [Docker Compose](https://docs.docker.com/compose/) which binds all the services needed to run the *n6* infrastructure.

```bash
docker compose build
```

The result of the process are ready-to-use docker images.

!!! tip

    Sometimes docker images might not be built correctly due to external factors.
    In case of any errors, try building them once more.

!!! note

    The Docker stack requires all images to be built correctly.
    In case of errors, please do not hesitate to create an
    [issue on our GitHub site](https://github.com/CERT-Polska/n6/issues).

If the build process has been correctly performed you should be able to
run the following command to obtain a result similar to what is listed
here:

```bash
docker images | grep n6
```

```
Output:
n6_mysql            latest              a34ee42c8e58        20 minutes ago      551MB
n6_rabbit           latest              841d42d17010        20 minutes ago      250MB
n6_web              latest              1f219d032515        21 minutes ago      2.39GB
n6_worker           latest              ec6c16c8bee5        22 minutes ago      1.67GB
n6_base             latest              1263daaf01e0        22 minutes ago      1.42GB
n6_mailhog          latest              8df1ccd08649        22 minutes ago      392MB
```

## Basic features of the prepared Docker stack

*n6*-specific Docker images to be run:

- `n6_worker` -- Python environment running the *n6* pipeline stuff (collectors, parsers etc.)
- `n6_mysql` -- MariaDB database instance, running the *n6*'s Event DB and Auth DB
- `n6_rabbit` -- RabbitMQ message broker
- `n6_web` -- *n6* services: REST API, Portal API+GUI, Admin Panel

Another image we also make use of:

- `n6_mongo:4.2` -- MongoDB database (NoSQL) running the *n6*'s Archive DB
- `n6_base` -- Dependencies running the *n6*'s

By default, the stack exposes the following ports:

- 80 -- redirects to 443 (to use HTTPS)
- 443 -- *n6* Portal GUI + *n6* Portal API (`/api`)
- 3001 -- *n6* Portal GUI parameterization configurator
- 4443 -- *n6* REST API
- 4444 -- *n6* Admin Panel
- 1025 -- Mailhog SMTP Server
- 8025 -- Mailhog Web GUI
- 15671 -- RabbitMQ Management

!!! note

    Make sure that all ports are not used by your localhost.
    If a port is used by another service, please change it in the
    `docker compose.yml` file and for GUI parameterization configurator
    you also need to change port in `run_app_server.js` in `N6Porta/reactapp/config/`

## Launching the system

To start the *n6* environment, execute:

```bash
docker compose up
```

Now, give Docker a few minutes to initialize.

!!! tip

    You can use the `-d` flag to run the application in the background (*detached mode*).

Port  **3001** is used by the Portal GUI parameterization configurator.
It is not necessary for n6 to work. Therefore to use it you need to set it up manually:

```bash
docker compose exec web bash
```

Then

```bash
cd /home/dataman/n6/N6Portal/react_app && yarn run config
```

### First startup

At first run you have to create the Auth DB database tables and its
schema. To create the tables use the `n6create_and_initialize_auth_db`
script (use the `-D` flag to first drop any existing Auth DB tables, and
the `-y` flag to suppress any confirmation prompts):

```bash
docker compose run --rm worker n6create_and_initialize_auth_db -D -y
```
```
Output:
* The 'n6create_and_initialize_auth_db' script started.
* Dropping the auth database if it exists...
[...]
* Creating the new auth database...
* Creating the new auth database tables...
* Inserting new `criteria_category` records...
  * CriteriaCategory "amplifier"
  * CriteriaCategory "bots"
  * CriteriaCategory "backdoor"
  * CriteriaCategory "cnc"
  * CriteriaCategory "deface"
  * CriteriaCategory "dns-query"
  * CriteriaCategory "dos-attacker"
  * CriteriaCategory "dos-victim"
  * CriteriaCategory "flow"
  * CriteriaCategory "flow-anomaly"
  * CriteriaCategory "fraud"
  * CriteriaCategory "leak"
  * CriteriaCategory "malurl"
  * CriteriaCategory "malware-action"
  * CriteriaCategory "other"
  * CriteriaCategory "phish"
  * CriteriaCategory "proxy"
  * CriteriaCategory "sandbox-url"
  * CriteriaCategory "scam"
  * CriteriaCategory "scanning"
  * CriteriaCategory "server-exploit"
  * CriteriaCategory "spam"
  * CriteriaCategory "spam-url"
  * CriteriaCategory "tor"
  * CriteriaCategory "vulnerable"
  * CriteriaCategory "webinject"
* Invoking appropriate Alembic tools to stamp the auth database as being at the `head` Alembic revision...
[...]
* The 'n6create_and_initialize_auth_db' script exits gracefully.
```

Here you go! *n6* is ready to use.

But, please, read on (to learn, in particular, how to get into *n6*...).

### Populating the Auth DB with example data

Let us add some example data to the Auth DB, in particular, creating an example user and its organization.
You will be prompted to enter the user's password. Remember it. You will need it to log in to the n6 Portal.

```bash
docker compose run --rm worker n6populate_auth_db -F -i -t -s -p example.com login@example.com
```

To see the results, restart (or reload) the `apache2` service:

```bash
docker compose exec web apache2ctl restart
```

!!! warning "As mentioned in the disclaimer"
    This is not a production setup, so it may produce error:

    ```
    AH00558: apache2: Could not reliably determine the server's fully qualified domain name, using 192.168.32.5. Set the 'ServerName' directive globally to suppress this message
    ```

    For local development or testing of n6 you can simply ignore it.

Then you can try the _n6 Admin Panel's_ interface: `https://localhost:4444/org`.
There should be new records in the following Auth DB tables: `org`,
`user`, `source`, `subsource`.

!!! tip
    In case you ever forgot password typed while populating auth_db.
    You can always change it in _admin panel_ -> _user_.

### Multi-Factor Authentication Setup

In your browser, type URL _https://localhost/_, where the password authentication pages will appear.
Insert credentials to log in. Login: _login@example.com_ and _password configured while creating account_.
Then follow the directions in _Multi-Factor Authentication Setup_.

## Checking availability of services and monitoring the system

**RabbitMQ Management (with RabbitMQ-generated GUI):**

- URL: [https://localhost:15671/](https://localhost:15671/)
- login: `guest`
- password: `guest`

**n6 Admin Panel:**

- URL: [https://localhost:4444/org](https://localhost:4444/org)

**n6 Portal API user authentication status:**

- URL: [https://localhost/api/info](https://localhost/api/info)

**n6 Portal GUI:**

- URL: [https://localhost/](https://localhost/)

- Credentials to log in:
    - username: `login@example.com`,
    - organization: `example.com`,
    - password: `entered when calling the n6populate_auth_db script`.

**Mailhog Web GUI:**

- URL: [https://localhost:8025/](https://localhost:8025/)


### Additional tools

**MongoDB Compass / Studio 3T Free - client GUI for MongoDB:**

- Connection:
    - name: any, e.g.: `n6-open`
    - hostname: `localhost`
    - port: `27017`

- Authentication:
    - database name: `n6` or `admin`
    - username: `admin`
    - password: `password`
    - auth mechanism: `MONGODB-CR` or `Default` in MongoDB Compass

## Working with Docker environment

Start `worker` container in the interactive mode:

```bash
docker compose exec worker bash
```

First, look at the container's directory structure:

```bash
ls -l
```
```
Output:
drwxr-xr-x 3 dataman dataman     4096 Jan 27 10:18 certs
-rwxr-xr-x 1 dataman dataman       80 Jan 27 10:19 entrypoint.sh
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:18 env
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:22 logs
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:19 n6
-rw-r--r-- 1 dataman dataman 39026234 Jan 27 10:19 node_modules.tar.gz
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:22 supervisord
drwxr-xr-x 2 dataman dataman     4096 Jan 27 10:17 tmp
```

Some files and directories are worth mentioning -- namely:

- the **`entrypoint.sh`** script wraps the given command, adding a
  necessary Python environment. It is used on every run/execution
  of the `worker` image. For example, we can run a *n6* collector
  script in two ways:

  - `docker compose exec worker ./entrypoint.sh n6collector_certplshield`
    or
  - `docker compose exec worker bash` and then `./entrypoint.sh n6collector_certplshield`

!!! note
    You could also go with `docker compose run worker ...`, but keep in mind that it will
    create new worker container. While using **run** command, you don't need to use `./entrypoint.sh` before `n6collector_certplshield`.

- the **`logs`** directory contains log files created by *n6* components.
  Every collector, parser or other *n6* component will write its logs
  here.

!!! note
    The `logs` directory will be lost on every container stop. You can
    use the Docker's _volumes_ feature to make the directory persistent.

- the **`supervisord`** directory contains Supervisor-related configuration
  files; the subdirectory **`programs`** contains a list of *n6* components
  that will be run by the _supervisord_ process. You are free to **mount
  the `programs` directory as a _volume_ into the container** and add more
  parsers.

- the **`n6`** directory contains the cloned repository. The *n6*
  infrastructure has been installed with the `develop` option. This
  means that you can mount the whole locally cloned `n6` directory
  as a _volume_ into the container. As a result, every change in locally
  stored *n6* code will be immediately applied inside the container on
  every `docker compose run <n6parser/n6collector/n6component>` (without the need
  to reinstall *n6* each time).

## Supervisor

!!! note

    This setup requires running `docker compose up`.

Run `supervisorctl` to examine the status of all n6 components:

```bash
docker compose exec worker supervisorctl -c supervisord/supervisord.conf
```
```
Output:
n6aggregator                         RUNNING   pid 34, uptime 0:05:55
n6archiveraw                         RUNNING   pid 35, uptime 0:05:55
n6comparator                         RUNNING   pid 36, uptime 0:05:55
n6enrich:n6enrich_00                 RUNNING   pid 37, uptime 0:05:55
n6filter:n6filter_00                 RUNNING   pid 38, uptime 0:05:55
n6log_std                            RUNNING   pid 42, uptime 0:05:53
n6parser_abusechfeodotracker202110   RUNNING   pid 40, uptime 0:05:55
n6recorder                           RUNNING   pid 41, uptime 0:05:55
```

Running the container initializes and starts processes configured to be
run by Supervisor.

Components being run by Supervisor work as daemon processes. Running
a parser triggers creation of a per-data-source RabbitMQ queue.

## Collecting data

In the interactive mode, after executing `source ./entrypoint.sh`, you can type,
in bash, `n6` + the `TAB` key to see all available *n6* executable scripts.
To see some data flowing through components via message broker,
run one of the collectors, e.g.:`n6collector_certplshield`.

```bash
docker compose exec worker bash
```
```bash
source ./entrypoint.sh
```
```bash
n6collector_certplshield
```

Now you can log in to the n6 portal and:

- go to **All Incidents** page.
- click the **events** tab.
- press **search** button (you can also set start date on datepicker).

and Events will load. If you used different collectors you can also add filters to search events. To see more detailed information on how n6 store the data, you might want to connect to MariaDB database via terminal or GUI client.

## Using REST API

*n6* provide you with REST API, but to use it you need to set your *API key*.

### Setting API Key

To set your *API key* follow these steps:

- Log into *n6* Portal.
- Click the user icon located in the top right corner.
- Go to user settings.
- Under multi-factor authentication you will see API key section.
- Click **generate key**.
- Now you can click on the generated key to copy it to clickboard.

Then you can make a request to the REST API, for example to obtain the collected
data (if any) for the current user, do:

```bash
docker compose exec worker bash
```
```bash
curl -k 'https://web:4443/search/events.json?time.min=2015-01-01T00:00:00' -H 'Authorization: Bearer YOUR_API_KEY'
```

And you should see some json data.

!!! note

    Initially, as in the case of Portal, there is no data available via
    REST API. To fetch and view some data, you need to run a collector
    -- for example, by executing `n6collector_certplshield`.

## Shutdown and cleanup

Stop and remove all containers, network bridge and Docker images:

```bash
docker compose down --rmi all -v
```

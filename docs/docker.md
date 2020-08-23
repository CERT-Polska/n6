# Docker-Based Installation Guide

This short guide describes how to run, for testing and learning, the
latest version of *n6*, with *Docker* and *Docker Compose*.

The goal of this guide is to give you an example of how you can glue the
relevant elements together in an easy way, so that you can learn -- by
monitoring and experimenting with the stuff -- how the *n6* system works
and how you can interact with it.


## Important: what these materials *are* and what they are *not*

This installation guide, as well as the stuff you can find in the `etc/`
and `docker/` directories of the *n6* source code repository, concern
setting up an *n6* instance just for testing, exploration and
experimentation, that is, **not for production** (at least, *not*
without a careful security-focused adjustment).

In other words, these materials are *not* intended to be used as a
recipe for a secure production setup -- in particular, when it comes to
(but not limited to) such issues as X.509 certificates (note that those
in the `etc/ssl/` directory of the source code repository are purely
example ones), authentication and authorization settings (which in these
materials are, generally, either skipped or reduced to what is necessary
just to run the stuff), or file access permissions.

It should be obvious that an experienced system administrator and/or
security specialist should prepare and/or carefully review and adjust
any configuration/installation/deployment of services that are to be
made production ones, in particular if those services are to be made
public.


## Requirements

- *Docker* installed (the newest version)
- *Docker Compose* installed (the newest version)
- The *n6* source code repository cloned


## Building the environment

> Note: Make sure you are in n6 directory

To build our demonstrational _n6_ environment we use [Docker Compose](https://docs.docker.com/compose/) which binds all the services needed to run the *n6* infrastructure.

```bash
$ docker-compose build
```

The result of the process are ready-to-use docker images.

> Note: the Docker stack requires all images to be built correctly.
> In case of errors, please do not hesitate to create an
> [issue on our GitHub site](https://github.com/CERT-Polska/n6/issues).

If the build process has been correctly performed you should be able to
run the following command to obtain a result similar to what is listed
here:

```bash
$ docker images | grep n6
n6_mysql            latest              a34ee42c8e58        20 minutes ago      376MB
n6_rabbit           latest              841d42d17010        20 minutes ago      181MB
n6_web              latest              1f219d032515        21 minutes ago      1.39GB
n6_worker           latest              ec6c16c8bee5        22 minutes ago      1.23GB
n6_base             latest              1263daaf01e0        22 minutes ago      1.23GB
```


## Basic features of the prepared Docker stack

*n6*-specific Docker images to be run:

* `n6_worker` -- Python environment running the *n6* pipeline stuff (collectors, parsers etc.)
* `n6_mysql` -- MariaDB database instance, running the *n6*'s Event DB and Auth DB
* `n6_rabbit` -- RabbitMQ message broker
* `n6_web` -- *n6* services: REST API, Portal API+GUI, Admin Panel

Another image we also make use of:

* `mongo:4.2` -- MongoDB database (NoSQL) running the *n6*'s Archive DB

By default, the stack exposes the following ports:

* 80 -- redirects to 443 (to use HTTPS)
* 443 -- *n6* Portal GUI + *n6* Portal API (`/api`)
* 4443 -- *n6* REST API
* 4444 -- *n6* Admin Panel
* 15671 -- RabbitMQ Management

> Note: Make sure that all ports are not used by your localhost.
> If a port is used by another service, please change it in the
> `docker-compose.yml` file.


## Launching the system

To start the n6 environment:

```bash
$ docker-compose up
```

Now, give Docker a few minutes to initialize.

After that, you can add the `-d` flag to run the stuff in the background
(*detached mode*).


### First startup

At first run you have to create the Auth DB database tables and its
schema. To create the tables use the `n6create_and_initialize_auth_db`
script (use the `-D` flag to first drop any existing Auth DB tables, and
the `-y` flag to suppress any confirmation prompts):

```bash
$ docker-compose run worker n6create_and_initialize_auth_db -D -y
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

Here you go! _n6_ is ready to use.

But, please, read on (to learn, in particular, how to get into _n6_...).


### Populating the Auth DB with example data

Let us add some example data to the Auth DB, in particular, creating an example user and its organization:

```bash
$ docker-compose run worker n6populate_auth_db -F -i -t -s example.com login@example.com
```

> **Warning**! If it's your first try with *n6*, do not modify the example
> organization and user identifiers specified above.  Currently the Docker
> setup uses certificates generated exactly for a user whose login is
> `login@example.com` and whose organization id is `example.com`.

To see the results, restart (or reload) the `apache2` service:

```bash
$ docker-compose exec web apache2ctl restart
```

Then go to _n6 Admin Panel's_ interface: `https://localhost:4444/org`.
There should be new records in the following Auth DB tables: `org`,
`user`, `source`, `subsource`.


### Adding a client certificate to your browser

In your web browser, choose _Preferences_ -> _Certificates_ (or whatever
other way your browser provides to manage certificates) and import our
example certificate from the
`etc/ssl/generated_certs/ImportMeToWebBrowser.p12` file.

This certificate allows you to sign in to the _n6 Portal_ GUI at `https://localhost`.


## Working with Docker environment

Start `worker` container in the interactive mode:

```bash
$ docker-compose exec worker bash
```

First, look at the container's directory structure:

```bash
$ ls -l
drwxr-xr-x 3 dataman dataman     4096 Jan 27 10:18 certs
-rwxr-xr-x 1 dataman dataman       80 Jan 27 10:19 entrypoint.sh
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:18 env
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:22 logs
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:19 n6
-rw-r--r-- 1 dataman dataman 39026234 Jan 27 10:19 node_modules.tar.gz
drwxr-xr-x 1 dataman dataman     4096 Jan 27 10:22 supervisord
drwxr-xr-x 2 dataman dataman     4096 Jan 27 10:17 tmp
```

Some files and directories worth mentioning are:

- the **entrypoint.sh** script wraps the given command, adding a
  necessary Python environment.  It is used on every run/execution
  of the `worker` image.  For example, we can run an *n6* collector
  script in two ways:

    - `docker-compose run worker n6collector_spam404`
    - `docker-compose run worker bash` and then `./entrypoint.sh n6collector_spam404`

- the **certs** directory contains certificate files, used as server
  certificates for authentication.  Those certificates are used by
  _RabbitMQ_ or Apache2-hosted services (such as _n6 REST API_ or
  _n6 Portal_). The server authentication certificate file with the
  subject `/CN=login@example.com/O=example.com` is generated by the
  script `n6/etc/ssl/generate_certs.sh`, and signed by the CA
  certificate (`/CN=n6-CA`) from the **n6-CA** subdirectory.

  **These certificates are provided only for demonstration
  purposes.  Using them in any production environment would be
  extremely wrong from the point of view of security!**

- the **logs** directory contains log files created by _n6_ components.
  Every collector, parser or other _n6_ component will write its logs
  here.

  **This directory will be lost on every container stop.  You can use
  the Docker's _volumes_ feature to make the directory persistent.**

- the **supervisord** directory contains Supervisor-related configuration
  files; the subdirectory **programs** contains a list of _n6_ components
  that will be run by the _supervisord_ process.  You are free to **mount
  the _programs_ directory as a _volume_ into the container** and add more
  parsers.
  
- the **n6** directory contains the cloned repository. The _n6_
  infrastructure has been installed with the `develop` option. This
  means that you can mount the whole locally cloned _n6_ directory
  as a _volume_ into the container. As a result, every change in locally
  stored _n6_ code will be immediately applied inside the container on
  every `docker-compose run  <n6parser/collector/etc>` (without the need
  to reinstall _n6_ each time).


## Supervisor

> This setup requires running `docker-compose up`

Run `supervisorctl` to examine the status of all n6 components:

```bash
$ docker-compose run worker supervisorctl -c supervisord/supervisord.conf
n6aggregator                         RUNNING   pid 63, uptime 0:24:12
n6archiveraw                         RUNNING   pid 62, uptime 0:24:12
n6comparator                         RUNNING   pid 70, uptime 0:24:12
n6filter:n6filter_00                 RUNNING   pid 68, uptime 0:24:12
n6log_std                            RUNNING   pid 90, uptime 0:24:11
n6parser_abusechfeodotracker201908   RUNNING   pid 65, uptime 0:24:12
n6parser_abusechsslblacklist201902   RUNNING   pid 64, uptime 0:24:12
n6parser_abusechurlhausurls202001    RUNNING   pid 69, uptime 0:24:12
n6parser_zonehrss                    RUNNING   pid 66, uptime 0:24:12
n6recorder                           RUNNING   pid 71, uptime 0:24:12
```

Running the container initializes and starts processes configured to be
run by Supervisor.

Components being run by Supervisor work as daemon processes.  Running
any parsers triggers creating of RabbitMQ per-data-source queues.

In the interactive mode you can type, in bash, `n6` + the `TAB` key to
see all available _n6_ executable scripts. To see some data flowing
through components via message broker, run one of the collectors, e.g.:
`n6collector_abusechfeodotracker`.

Then make a request to the REST API, for example to obtain the collected
data (if any) for the current user, do:

```bash
$ docker-compose run worker bash
$ curl --cert certs/cert.pem --key certs/key.pem -k 'https://web:4443/search/events.json?time.min=2015-01-01T00:00:00'
```


## Checking availability of services and watching the system

**RabbitMQ Management (with RabbitMQ-generated GUI):**

* URL: https://localhost:15671/
* login: `guest`
* password: `guest`

**n6 Admin Panel:**

* URL: [https://localhost:4444/org](https://localhost:4444/org)

**n6 Portal API user authentication status:**

* URL: [https://localhost/api/info](https://localhost/api/info)

**n6 Portal GUI:**

* URL: [https://localhost/](https://localhost/)

* _TBD (for now, not enabled)_ ~~Credentials to log in, when using login+password authentication: * username: `login@example.com`, * organization: `example.com`, * password: `aaaa`.~~

#### Additional tools

**Robomongo - client GUI for MongoDB:**

* Connection:

    * name: any, e.g.: "n6-open"
    * hostname: `localhost`
    * port: `27017`

* Authentication:

    * database name: `n6` or `admin`
    * username: `admin`
    * password: `password`
    * auth mechanism: `MONGODB-CR`

**MongoDB - interactive mode:**

```bash
$ docker-compose exec mongo bash
$ mongo --host mongo n6 -u admin -p password
```

**MySQL Workbench - client GUI for SQL database:**

* Connection name: any, e.g.: "Local n6 instance"
* Connection method: Standard TCP/IP
* Hostname: `localhost`
* Port: `3306`
* Username: `root`

**MySQL - Interactive mode:**

```bash
$ docker-compose exec mysql bash
$ mysql --host mysql --user root -ppassword
```


## Shutdown and cleanup

Stop and remove all containers, network bridge and Docker images:
```bash
$ docker-compose down --rmi all -v
```

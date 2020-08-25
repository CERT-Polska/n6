# System Preparation

## RabbitMQ

RabbitMQ is an open source message broker software (sometimes called message-oriented middleware)
that implements the Advanced Message Queuing Protocol (AMQP). RabbitMQ is responsible for
communication between most of the *n6* components.

### Setup

```bash
$ apt-get install gnupg2 apt-transport-https curl
$ curl https://dl.bintray.com/rabbitmq/Keys/rabbitmq-release-signing-key.asc | apt-key add -
$ echo "deb https://dl.bintray.com/rabbitmq/debian buster main" | tee /etc/apt/sources.list.d/bintray.rabbitmq.list
$ echo "deb https://dl.bintray.com/rabbitmq-erlang/debian buster erlang-22.x" | sudo tee -a /etc/apt/sources.list.d/bintray.erlang.list 
$ apt-get update
$ apt-get install rabbitmq-server
```

RabbitMQ is by default attached to `systemd` and is running after an installation.
To see if `rabbitmq-server` process is running, check its status through the `systemctl` command,
its value should be: `active (running)`:

```bash
$ systemctl status rabbitmq-server
● rabbitmq-server.service - RabbitMQ broker
   Loaded: loaded (/lib/systemd/system/rabbitmq-server.service; enabled; vendor preset:
   Active: active (running) since Fri 2020-01-10 16:32:54 CET; 12min ago
 Main PID: 4771 (beam.smp)
   Status: "Initialized"
    Tasks: 84 (limit: 4689)
   Memory: 94.9M
   CGroup: /system.slice/rabbitmq-server.service
           ├─4771 /usr/lib/erlang/erts-10.6.1/bin/beam.smp -W w -A 64 -MBas ageffcbf -M
           ├─5019 erl_child_setup 32768
           ├─5042 inet_gethost 4
           └─5043 inet_gethost 4
```

### Plugins
Enable necessary plugins, like SSL or management panel plugin:

```bash
$ /usr/sbin/rabbitmq-plugins enable \
    rabbitmq_management \
    rabbitmq_management_agent \
    rabbitmq_auth_mechanism_ssl \
    rabbitmq_federation \
    rabbitmq_federation_management \
    rabbitmq_shovel \
    rabbitmq_shovel_management

The following plugins have been configured:
  rabbitmq_auth_mechanism_ssl
  rabbitmq_federation
  ...

Applying plugin configuration to rabbit@pw-ups02...
The following plugins have been enabled:
  rabbitmq_auth_mechanism_ssl
  rabbitmq_federation
  ...

started 8 plugins.
```

### Configuration

If you do not provide a configuration file for RabbitMQ, default values will be used. Or you
can use the example configuration from `n6/etc/rabbitmq/conf/rabbitmq.conf`, by copying
the file to `/etc/rabbitmq`. Restart the `rabbitmq-server` process afterwards:

```bash
$ sudo service rabbitmq-server restart
```

To ensure everything is OK, sign in to the RabbitMQ web management interface through your
web browser. The default address is `http://localhost:15672`, or `https://localhost:15671`
if you have used the example config. You can use default `guest` credentials:

```text
default user: guest     
default password: guest
```

Or you can create a new user, allow him to use the *Management GUI* and give him read/write
permissions to resources within `/` vhost:

```bash
$ sudo rabbitmqctl add_user <username> <password>
$ sudo rabbitmqctl set_user_tags <username> management
$ sudo rabbitmqctl set_permissions -p / example ".*" ".*" ".*"
```

To make the new user an administrator, set him the `administrator` tag:

```bash
$ sudo rabbitmqctl set_user_tags <username> administrator
```

## MariaDB

*n6* uses two SQL databases - event database and *Auth DB*.
The event database primarily stores processed information about network events and possible
security incidents, also their relation to organizations linked to clients.
The *Auth DB* database is used for client authorization. It stores clients' permissions
and information about allowed resources (allowed API endpoints, allowed *subsources*).

```bash
$ apt-key adv --recv-keys --keyserver keyserver.ubuntu.com 0xF1656F24C74CD1D8
$ add-apt-repository 'deb http://sfo1.mirrors.digitalocean.com/mariadb/repo/10.3/debian buster main'
$ apt-get update
$ apt-get install dirmngr \
    libjemalloc-dev \
    libjemalloc2 \
    mariadb-server-10.3 \
    mariadb-plugin-tokudb \
    software-properties-common
```

Check whether `mariadb` is controlled by `systemd`. To check whether `mariadb` is
running, look for its status, it should be `active`.

```bash
# systemctl status mariadb
● mariadb.service - MariaDB 10.3.21 database server
   Loaded: loaded (/lib/systemd/system/mariadb.service; enabled; vendor preset: enabled)
  Drop-In: /etc/systemd/system/mariadb.service.d
           └─migrated-from-my.cnf-settings.conf, tokudb.conf
   Active: active (running) since Wed 2020-01-15 14:24:36 CET; 14s ago
     Docs: man:mysqld(8)
           https://mariadb.com/kb/en/library/systemd/
  Process: 6640 ExecStartPre=/usr/bin/install -m 755 -o mysql -g root -d /var/run/mysqld (code=exited, status=0/SUCCESS)
  Process: 6641 ExecStartPre=/bin/sh -c systemctl unset-environment _WSREP_START_POSITION (code=exited, status=0/SUCCESS)
  Process: 6643 ExecStartPre=/bin/sh -c [ ! -e /usr/bin/galera_recovery ] && VAR= ||   VAR=`/usr/bin/galera_recovery`; [ $? -eq 0 ]   && systemctl set-environment _WSREP_START_POSITION=$VAR || exit 1 (code=exite
  Process: 6689 ExecStartPost=/bin/sh -c systemctl unset-environment _WSREP_START_POSITION (code=exited, status=0/SUCCESS)
  Process: 6691 ExecStartPost=/etc/mysql/debian-start (code=exited, status=0/SUCCESS)
 Main PID: 6655 (mysqld)
   Status: "Taking your SQL requests now..."
    Tasks: 32 (limit: 4689)
   Memory: 92.2M
   CGroup: /system.slice/mariadb.service
           └─6655 /usr/sbin/mysqld
```


### Initialize system database

In this step we create databases and their tables. Stop database's processes:

```bash
# systemctl stop mariadb
```

The `-u` argument passes a username by which the `mysql` will be run as:

```bash
# /usr/bin/mysql_install_db -u mysql
Installing MariaDB/MySQL system tables in '/var/lib/mysql' ...
OK

...
You can find additional information about the MySQL part at:
http://dev.mysql.com
Consider joining MariaDB's strong and vibrant community:
https://mariadb.org/get-involved/
```

### Troubleshooting

#### [ERROR] TokuDB is not initialized because jemalloc is not loaded

There are a few solutions. Check for
[Check for Transparent HugePage Support on Linux](https://mariadb.com/kb/en/library/installing-tokudb/#check-for-transparent-hugepage-support-on-linux) and this section [about libjemalloc](https://mariadb.com/kb/en/library/installing-tokudb/#libjemalloc).

Make sure that you have installed `libjemalloc` library:

```bash
$ apt-get install -y libjemalloc2
```

Find location of `libjemalloc2`:

```bash
$ ls -l /usr/lib/x86_64-linux-gnu/ | grep libjemalloc
-rw-r--r--  1 root root   646352 Feb 23  2019 libjemalloc.so.2
```

Edit its location in `/etc/mysql/mariadb.conf.d/tokudb.cnf` as follows:

```ini
[mysqld_safe]
malloc-lib= /usr/lib/x86_64-linux-gnu/libjemalloc.so.2
```

Check for _Transparent HugePage Support_. It should be disabled - option [never]

```bash
$ cat /sys/kernel/mm/transparent_hugepage/enabled
always madvise [never]
```

You can disable it with:

```bash
$ echo never > /sys/kernel/mm/transparent_hugepage/enabled
$ echo never > /sys/kernel/mm/transparent_hugepage/defrag
```

Try the system database initialization script again:

```bash
$ LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2 /usr/bin/mysql_install_db -u mysql
```

Start database processes again:

```bash
$ systemctl start mariadb
```

Make sure you have access to database:

```bash
$ mysql -u root -p<your_password>
```

Check that the `tokudb` plugin is active in MySQL prompt:

```bash
> show plugins;
...
TokuDB
TokuDB_user_data
TokuDB_user_data_exact
TokuDB_file_map
TokuDB_fractal_tree_info
TokuDB_fractal_tree_block_map
```


## MongoDB

*n6* uses MongoDB as archival database. Events gathered by collectors will be stored in MongoDB
and can be restored in case of errors.

Installation steps below are based on
[Install MongoDB Community Edition on Debian](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-debian/)
solution.

To install MongoDB do the following (as root):

```bash
$ wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | sudo apt-key add -
$ echo "deb http://repo.mongodb.org/apt/debian buster/mongodb-org/4.2 main" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.2.list
$ apt-get update
$ apt-get install -y mongodb-org
```

Check MongoDB version. *n6* supports versions `4.2.*`:

```bash
$ mongod --version
db version v4.2.3
git version: a0bbbff6ada159e19298d37946ac8dc4b497eadf
OpenSSL version: OpenSSL 1.1.1d  10 Sep 2019
allocator: tcmalloc
modules: none
build environment:
    distmod: debian10
    distarch: x86_64
    target_arch: x86_64
```

Create a default storage for MongoDB:

```bash
$ mkdir -p /data/db
```

Try to run the `mongod` process:

```bash
$ mongod
```

Successfull output should looks similar to the output below:

```bash
$ mongod
2019-09-05T14:20:54.360+0200 I STORAGE  [main] Max cache overflow file size custom option: 0
2019-09-05T14:20:54.362+0200 I CONTROL  [main] Automatically disabling TLS 1.0, to force-enable TLS 1.0 specify --sslDisabledProtocols 'none'
2019-09-05T14:20:54.367+0200 I CONTROL  [initandlisten] MongoDB starting : pid=9303 port=27017 dbpath=/data/db 64-bit host=pw-ups02
2019-09-05T14:20:54.367+0200 I CONTROL  [initandlisten] db version v4.0.12
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten] git version: 5776e3cbf9e7afe86e6b29e22520ffb6766e95d4
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten] OpenSSL version: OpenSSL 1.1.1c  28 May 2019
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten] allocator: tcmalloc
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten] modules: none
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten] build environment:
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten]     distmod: debian92
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten]     distarch: x86_64
2019-09-05T14:20:54.368+0200 I CONTROL  [initandlisten]     target_arch: x86_64
...
2019-09-05T14:20:55.039+0200 I STORAGE  [initandlisten] createCollection: local.startup_log with generated UUID: 7f6a72d1-57a7-4b12-842d-cd2e91959df6
2019-09-05T14:20:55.069+0200 I FTDC     [initandlisten] Initializing full-time diagnostic data capture with directory '/data/db/diagnostic.data'
2019-09-05T14:20:55.085+0200 I NETWORK  [initandlisten] waiting for connections on port 27017
2019-09-05T14:20:55.088+0200 I STORAGE  [LogicalSessionCacheRefresh] createCollection: config.system.sessions with generated UUID: ebd42929-32e9-41e2-a818-8b0c6b8d7393
2019-09-05T14:20:55.132+0200 I INDEX    [LogicalSessionCacheRefresh] build index on: config.system.sessions properties: { v: 2, key: { lastUse: 1 }, name: "lsidTTLIndex", ns: "config.system.sessions", expireAfterSeconds: 1800 }
2019-09-05T14:20:55.132+0200 I INDEX    [LogicalSessionCacheRefresh] 	 building index using bulk method; build may temporarily use up to 500 megabytes of RAM
2019-09-05T14:20:55.136+0200 I INDEX    [LogicalSessionCacheRefresh] build index done.  scanned 0 total records. 0 secs
```

Terminate (Ctrl + C) and start MongoDB with `systemd`:

```bash
$ systemctl start mongod
$ systemctl status mongod
● mongod.service - MongoDB Database Server
   Loaded: loaded (/lib/systemd/system/mongod.service; disabled; vendor preset: enabled
   Active: active (running) since Tue 2020-01-14 18:12:21 CET; 1min 22s ago
     Docs: https://docs.mongodb.org/manual
 Main PID: 21281 (mongod)
   Memory: 81.6M
   CGroup: /system.slice/mongod.service
           └─21281 /usr/bin/mongod --config /etc/mongod.conf

Jan 14 18:12:21 debian systemd[1]: Started MongoDB Database Server.
``` 

Check if you are able to connect to MongoDB console:

```bash
$ mongo
MongoDB shell version v4.0.14
connecting to: mongodb://127.0.0.1:27017/?gssapiServiceName=mongodb
Implicit session: session { "id" : UUID("eeb1d020-955c-4b74-9c00-729c0da188f9") }
MongoDB server version: 4.2.3
....
>
```


## Apache HTTP Server

_n6_ uses Apache as an HTTP server for services like *n6 REST API*, *n6 Portal API*
or *n6 Admin Panel* `N6RestAPI` or `N6AdminPanel`.

```bash
$ sudo apt-get install apache2 libapache2-mod-wsgi
```

Check if the `apache2` service is ran by `systemd`: 

```bash
$ systemctl status apache2
● apache2.service - The Apache HTTP Server
   Loaded: loaded (/lib/systemd/system/apache2.service; enabled; vendor preset: enabled)
   Active: active (running) since Tue 2020-01-14 18:07:49 CET; 27min ago
     Docs: https://httpd.apache.org/docs/2.4/
 Main PID: 20852 (apache2)
    Tasks: 55 (limit: 4689)
   Memory: 13.7M
   CGroup: /system.slice/apache2.service
           ├─20852 /usr/sbin/apache2 -k start
           ├─20854 /usr/sbin/apache2 -k start
           └─20855 /usr/sbin/apache2 -k start

Jan 14 18:07:49 debian systemd[1]: Starting The Apache HTTP Server...
Jan 14 18:07:49 debian apachectl[20848]: AH00558: apache2: Could not reliably determine the server's fully qualified domain name, using 127.0.1.1. Set the 'ServerName' directive globally to suppress this message
Jan 14 18:07:49 debian systemd[1]: Started The Apache HTTP Server.
```

While `apache2` is running, enable required modules:

Enable modules:

```bash
$ /usr/sbin/a2enmod ssl
...
Enabling module socache_shmcb.
Enabling module ssl.
```

```bash
$ /usr/sbin/a2enmod rewrite
...
Enabling module rewrite.
```

To run modules you need to reload/restart `apache2`:

```bash
$ systemctl restart apache2
```


## Debian dependencies

You should install the essential Debian packages:

> Note: Add the "contrib" repository in `/etc/apt/sources.list` if needed.

```bash
$ sudo apt-get update
$ sudo apt-get install \
    build-essential \
    curl \
    default-libmysqlclient-dev \
    iputils-ping \
    ldap-utils \
    libapache2-mod-wsgi \
    libattr1-dev \
    libcurl4-openssl-dev \
    libffi-dev \
    libfuse-dev \
    libgeoip1 \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libyajl2 \
    nodejs \
    npm \
    pkg-config \
    python \
    python2.7-dev \
    python-ldap \
    python-mysqldb \
    python-pastedeploy \
    python-pip \
    python-pycurl \
    python-setuptools \
    python-virtualenv \
    rsyslog \
    ssh \
    sudo \
    supervisor \
    swig \
    wget
$ sudo apt-get clean
```

## Creating the _dataman_ user

Let *n6* be run by the `dataman` OS user.  First, let us create its
initial login group:

```bash
$ /usr/sbin/groupadd dataman
```

Now, when creating the `dataman` user, let us ensure that the user is
also added to the `www-data` group (so that access to *Apache*'s files
is granted).

```bash
$ /usr/sbin/useradd -rm \
    -d /home/dataman \
    -s /bin/bash \
    -p '' \
    -g dataman \
    -G www-data \
    dataman
```

We will keep the `n6` repository in the `dataman`'s home directory.

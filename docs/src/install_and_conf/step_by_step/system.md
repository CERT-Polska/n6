# System Preparation

## Basic requirements

The required operating system is a contemporary **GNU/Linux**
distribution. This installation guide assumes that you use **Debian 11
(Bullseye)**, with a non-root `dataman` user account created (there is a
section on how to create that user).

Moreover, the _n6_ infrastructure depends on:

- **RabbitMQ** (an AMQP message broker),
- **MariaDB** (a SQL database server) with the RocksDB engine.

To run some _n6_ components it is also required to have installed:

- **MongoDB** (a NoSQL database server),
- **Apache2** (a web server).

## Debian dependencies and tools

You should install the essential Debian packages:

```bash
$ sudo apt-get update && \
  sudo apt-get install -y \
        apt-transport-https \
        build-essential \
        curl \
        gnupg2 \
        libattr1-dev \
        libgeoip1 \
        libsqlite3-dev \
        libssl-dev \
        libmariadb-dev \
        libbz2-dev \
        libffi-dev \
        libyajl2 \
        python3 \
        python3-dev \
        python3-venv \
        python3-stemmer \
        rsyslog \
        ssh \
        supervisor \
        swig \
        systemd \
        virtualenv \
        wget \
        zlib1g-dev
$ sudo apt-get clean
```

## Creating the _dataman_ user

Let _n6_ be run by the `dataman` OS user. First, let us create its
initial login group:

```bash
$ sudo /usr/sbin/groupadd dataman
$ sudo /usr/sbin/useradd -rm \
    -d /home/dataman \
    -s /bin/bash \
    -p '' \
    -g dataman \
    dataman
```

We will keep the `n6` repository in the `dataman`'s home directory.

## RabbitMQ

RabbitMQ is an open source message broker software (sometimes called message-oriented middleware)
that implements the Advanced Message Queuing Protocol (AMQP). RabbitMQ is responsible for
communication between most of the _n6_ components.

### Setup

[Install RabbitMQ on Debian](https://www.rabbitmq.com/install-debian.html#apt-quick-start-packagecloud)
solution.

```bash
$ curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" | sudo gpg --dearmor | sudo tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null
$ curl -1sLf https://ppa.novemberain.com/gpg.E495BB49CC4BBE5B.key | sudo gpg --dearmor | sudo tee /usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg > /dev/null
$ curl -1sLf https://ppa.novemberain.com/gpg.9F4587F226208342.key | sudo gpg --dearmor | sudo tee /usr/share/keyrings/rabbitmq.9F4587F226208342.gpg > /dev/null
$ sudo tee /etc/apt/sources.list.d/rabbitmq.list <<EOF
deb [signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-erlang/deb/ubuntu jammy main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-erlang/deb/ubuntu jammy main
deb [signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa2.novemberain.com/rabbitmq/rabbitmq-erlang/deb/ubuntu jammy main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa2.novemberain.com/rabbitmq/rabbitmq-erlang/deb/ubuntu jammy main
deb [signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-server/deb/ubuntu jammy main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa1.novemberain.com/rabbitmq/rabbitmq-server/deb/ubuntu jammy main
deb [signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa2.novemberain.com/rabbitmq/rabbitmq-server/deb/ubuntu jammy main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa2.novemberain.com/rabbitmq/rabbitmq-server/deb/ubuntu jammy main
EOF
$ sudo apt-get update -y
$ sudo apt-get install -y erlang-base \
                        erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
                        erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
                        erlang-runtime-tools erlang-snmp erlang-ssl \
                        erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl
$ sudo apt-get install rabbitmq-server -y --fix-missing
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
$ sudo /usr/sbin/rabbitmq-plugins enable \
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
the file to `/etc/rabbitmq`. Replace the paths to the certificate files.

```text
ssl_options.cacertfile = /home/dataman/n6/etc/ssl/generated_certs/n6-CA/cacert.pem
ssl_options.certfile = /home/dataman/n6/etc/ssl/generated_certs/cert.pem
ssl_options.keyfile = /home/dataman/n6/etc/ssl/generated_certs/key.pem
```

Restart the `rabbitmq-server` process afterwards:

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

If you copied configuration file create a new user, allow them to use the _Management GUI_ and
give them read/write permissions to resources within `/` vhost.
Replace <username> in script below with `login@example.com`:

```bash
$ sudo rabbitmqctl add_user <username> <password>
$ sudo rabbitmqctl set_user_tags <username> management
$ sudo rabbitmqctl set_permissions -p / <username> ".*" ".*" ".*"
```

To make the new user an administrator, set him the `administrator` tag:

```bash
$ sudo rabbitmqctl set_user_tags <username> administrator
```

## Troubleshooting: [ERROR] rabbitmq-server failing to start

In case of issue with rabbitmq-server copy certificate files to different location, for example 
to /etc/rabbitmq, run chmod and change paths in `/etc/rabbitmq/rabbitmq.conf` accordingly:
```bash
$ sudo mkdir -p /etc/rabbitmq/certs/
$ sudo cp /home/dataman/n6/etc/ssl/generated_certs/n6-CA/cacert.pem /etc/rabbitmq/certs/
$ sudo cp /home/dataman/n6/etc/ssl/generated_certs/cert.pem /etc/rabbitmq/certs/
$ sudo cp /home/dataman/n6/etc/ssl/generated_certs/key.pem /etc/rabbitmq/certs/
$ sudo chmod -R 664 /etc/rabbitmq/certs/
```


## MariaDB

_n6_ uses two SQL databases - event database and _Auth DB_.
The event database primarily stores processed information about network events and possible
security incidents, also their relation to organizations linked to clients.
The _Auth DB_ database is used for client authorization. It stores clients' permissions
and information about allowed resources (allowed API endpoints, allowed _subsources_).

The required version of MariaDB is 10.3 which is not supported by Debian 11 using a package manager.
One of the installation methods is to use MariaDB Binary Tarballs.

To install MariaDB from Generic Binaries on Unix/Linux, download the appropriate binary version.
Go to _https://mariadb.org/download_, select and download MariaDB Server 10.3.x version
to _/home/dataman/Downloads_ directory.

You should install the essential Debian packages:

```bash
$ sudo apt update && \
  sudo apt install -y libaio1 libncurses5 libjemalloc2
```

Add the `mysql` group and the `mysql` user.

```bash
$ sudo groupadd mysql
$ sudo useradd -g mysql mysql
```

Create a directory to which you want to unpack the distribution and change your location
to the directory path. In the following example, we unpack the file to `/usr/local/mysql`.
(Therefore, the instructions assume that you have permission to create files and directories in
`/usr/local/mysql`. If that directory is protected, you must perform the installation as root.
Then unpack the distribution. The tar command unpacks the distribution to the `/usr/local/mysql/`.

```bash
$ sudo mkdir /usr/local/mysql
$ cd /usr/local/mysql
$ sudo tar -zxvpf /home/dataman/Downloads/mariadb-10.3.34-linux-systemd-x86_64.tar.gz -C /usr/local/mysql/ --strip-components 1
```

Most of the files installed by MariaDB may be owned by `root` if you like.
The data directory is the exception, it must be owned by `mysql` user.
To accomplish this, run the following commands as `root` in the installation directory.

```bash
$ sudo chown -R root .
$ sudo chown -R mysql data
```

You will find several files and subdirectories in the mysql directory.
The most important for installation purposes are the `bin` and `scripts` subdirectories.

MariaDB server can be configured through its main configuration file.
The default MariaDB option file is called `my.cnf`.
Create an empty `/etc/mysql/my.cnf` file and fill it with configuration content like below:

```bash
$ sudo mkdir /etc/mysql/
$ sudo touch /etc/mysql/my.cnf

# Minimal option file
# Run command as root
$ cat <<EOT > /etc/mysql/my.cnf
[client-server]
socket=/run/mysqld/mysqld.sock
port=3306

# This will be passed to all MariaDB clients
[client]
#password=my_password

# The MariaDB server
[mysqld]
# Directory under which is the distribution
basedir=/usr/local/mysql
# Directory where you store your data
datadir=/usr/local/mysql/data
# The name of the login account that you created in the first step to use for running the server.
user=mysql
# Directory for the errmsg.sys file in the language you want to use
language=/usr/local/mysql/share/english

# This is the prefix name to be used for all log, error and replication files
log-basename=mysqld

# Enable logging by default to help find problems
general-log

[mariadb]
plugin_load_add = ha_rocksdb

EOT
```

Create a directory for server through socket `/var/run/mysqld/mysqld.sock`:

```bash
$ sudo mkdir /run/mysqld/
$ sudo chown -R mysql:mysql /run/mysqld/
```

To initialize the MySQL database containing the grant tables that store the server access
permissions. The command should create the data directory and its contents
with mysql as the owner. After creating or updating the grant tables, you need to
restart the server manually.

```bash
$ sudo ./scripts/mysql_install_db --user=mysql
```

To start MariaDB automatically when you boot your machine, copy
`support-files/mysql.server` and `support-files/systemd/mariadb.service` to the location where
your system has its startup files.

```bash
$ sudo cp support-files/mysql.server /etc/init.d/mysql.server
$ sudo cp support-files/systemd/mariadb.service /usr/lib/systemd/system/mariadb.service
$ sudo systemctl daemon-reload
```

Note that by default the _/usr_ directory is write protected by systemd though, so when 
having the data directory in `/usr/local/mysql/data` as per the instructions above you 
also need to make that directory writable (as a root).

```bash
# Run command as root
$ mkdir /etc/systemd/system/mariadb.service.d/
$ cat > /etc/systemd/system/mariadb.service.d/datadir.conf <<EOF
[Service]
ReadWritePaths=/usr/local/mysql/data
EOF
$ systemctl daemon-reload
```

Modify the `$PATH` environment variable, so you can invoke commands such 
as `mysql`, `mysqldump`, etc.

```bash
$ echo "export PATH=${PATH}:/usr/local/mysql/bin" >> ~/.bashrc
$ bash
```

After everything has been unpacked and installed, you should test your distribution.
To start the MariaDB server, use the following command:

```bash
$ sudo ./bin/mysqld_safe --datadir='/usr/local/mysql/data' &
```

To set a password for the MariaDB root accounts, use the following command:

```bash
$ sudo ./bin/mysql_secure_installation --defaults-file=/etc/mysql/my.cnf
```

Then kill mysql process, to run the right way by `systemd`.

```bash
$ sudo pkill mysql
```

Check whether `mariadb` is controlled by `systemd`. To check whether `mariadb` is
running, look for its status, it should be `active`.

```bash
$ sudo systemctl status mysql
or
$ sudo service mysql.server status
● mysql.server.service - LSB: start and stop MariaDB
     Loaded: loaded (/etc/init.d/mysql.server; generated)
     Active: inactive (dead)
       Docs: man:systemd-sysv-generator(8)

Jan 04 03:42:02 pw-ups02 su[4770]: (to mysql) root on none
Jan 04 03:42:02 pw-ups02 su[4770]: pam_unix(su-l:session): session opened for user mysql(uid=1001) by (uid=0)
Jan 04 03:42:02 pw-ups02 su[4770]: pam_unix(su-l:session): session closed for user mysql
Jan 04 03:42:03 pw-ups02 su[4784]: (to mysql) root on none
Jan 04 03:42:03 pw-ups02 su[4784]: pam_unix(su-l:session): session opened for user mysql(uid=1001) by (uid=0)
Jan 04 03:42:03 pw-ups02 su[4784]: pam_unix(su-l:session): session closed for user mysql
Jan 04 03:42:03 pw-ups02 mysql.server[4577]: ....
Jan 04 03:42:03 pw-ups02 systemd[1]: mysql.server.service: Succeeded.
Jan 04 03:42:03 pw-ups02 systemd[1]: Stopped LSB: start and stop MariaDB.
Jan 04 03:42:03 pw-ups02 systemd[1]: mysql.server.service: Consumed 9.929s CPU time.
```

### Initialize system database

In this step we create databases and their tables.
Start database processes in case it is not active:

```bash
$ sudo systemctl start mysql
or
$ sudo service mysql.server start
```

Make sure you have access to the database:

```bash
$ mysql -u root -p<your_password>
```

Check that the `RocksDB` plugin is active in MySQL prompt:

```bash
> show plugins;
...
| ROCKSDB                       | ACTIVE   | STORAGE ENGINE     | ...
...
```

## MongoDB

_n6_ uses MongoDB as archival database. Events gathered by collectors will
be stored in MongoDB and can be restored in case of errors.

Installation steps below are based on
[Install MongoDB Community Edition on Debian](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-debian/)
solution.

Install libssl1.1

```bash
$ wget http://deb.debian.org/debian/pool/main/o/openssl/libssl1.1_1.1.0j-1~deb9u1_amd64.deb
$ sudo dpkg -i libssl1.1_1.1.0j-1~deb9u1_amd64.deb
$ rm -i libssl1.1_1.1.0j-1~deb9u1_amd64.deb
```

To install MongoDB, do the following (as `root`):

```bash
$ wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | sudo apt-key add -
$ sudo apt-get update
$ sudo apt-get install -y mongodb-org
```

Try to start MongoDB with `systemd`:

```bash
$ sudo systemctl start mongod
```

Successful output should look similar to the output below:

```bash
$ sudo systemctl status mongod
● mongod.service - MongoDB Database Server
     Loaded: loaded (/lib/systemd/system/mongod.service; disabled; vendor preset: enabled)
     Active: active (running) since Wed 2022-01-26 05:17:13 EST; 5min ago
       Docs: https://docs.mongodb.org/manual
   Main PID: 5537 (mongod)
     Memory: 72.0M
        CPU: 2.597s
     CGroup: /system.slice/mongod.service
             └─5537 /usr/bin/mongod --config /etc/mongod.conf

Jan 26 05:17:13 pw-ups02 systemd[1]: Started MongoDB Database Server.
```

Check if you are able to connect to MongoDB console:

```bash
$ mongo
MongoDB shell version v4.2.18
connecting to: mongodb://127.0.0.1:27017/?compressors=disabled&gssapiServiceName=mongodb
Implicit session: session { "id" : UUID("a6f4ca5e-eab1-4e65-9c3e-4e9f877a4e45") }
MongoDB server version: 4.2.18
....
>
```

## Apache HTTP server

_n6_ uses Apache as an HTTP server for services like _n6 REST API_,
_n6 Portal API_ or _n6 Admin Panel_ `N6RestAPI` or `N6AdminPanel`.

```bash
$ sudo apt update && \
  sudo apt install -y apache2 libapache2-mod-wsgi-py3 
```

Check if the `apache2` service is run by `systemd`:

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
$ sudo /usr/sbin/a2enmod ssl
...
Enabling module socache_shmcb.
Enabling module ssl.
```

```bash
$ sudo /usr/sbin/a2enmod rewrite
...
Enabling module rewrite.
```

To run modules you need to reload/restart `apache2`:

```bash
$ sudo systemctl restart apache2
```

## Arrangements related to Apache

Add `dataman` to the `www-data` group, make the necessary directories,
and set appropriate permissions:

```bash
$ sudo /usr/sbin/usermod -a -G dataman www-data
$ mkdir -p /home/dataman/env_py3k/.python-eggs
$ sudo chown -R dataman:www-data /home/dataman/env_py3k
$ sudo chmod 775 /home/dataman/env_py3k/.python-eggs
$ sudo chown -R www-data:www-data /etc/apache2/sites-available/
```

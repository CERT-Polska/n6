# System Preparation

## Basic requirements

The required operating system is a contemporary **GNU/Linux**
distribution. This installation guide assumes that you use **Debian 12
(Bookworm)**, with a non-root `dataman` user account created (there is a
section on how to create that user).

Moreover, the _n6_ infrastructure depends on:

- **RabbitMQ** (an AMQP message broker),
- **MariaDB** (a SQL database server) with the RocksDB engine.

To run web server of _n6_ it is also required to have installed:

- **Apache2** (a web server).

Additionally to archive your data using *n6archiver*:

- **MongoDB** (a NoSQL database server),

## Debian dependencies and tools

You should install the essential packages:

```bash
$ sudo apt update && \
  sudo apt install -y \
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
$ sudo apt clean
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
    -G sudo,www-data \
    dataman
```
For convinence you can add `dataman` to `/etc/sudoers`.
However you might want to make `dataman` as a *non-privileged-user* after you set up *n6* instance.
```bash
dataman	ALL=(ALL:ALL) NOPASSWD:ALL
```

We will keep the `n6` repository in the `dataman`'s home directory.

## Cloning *n6* repository.

Clone the `n6` repository into the `dataman`'s home directory.
For example (git required):

```bash
$ git clone https://github.com/CERT-Polska/n6.git /home/dataman/n6/
```

## RabbitMQ

RabbitMQ is an open source message broker software (sometimes called message-oriented middleware)
that implements the Advanced Message Queuing Protocol (AMQP). RabbitMQ is responsible for
communication between most of the _n6_ components.

### Setup

[Install RabbitMQ on Debian](https://www.rabbitmq.com/install-debian.html#apt-quick-start-packagecloud)
solution.

```bash
#!/bin/sh

sudo apt install curl gnupg apt-transport-https -y

## Team RabbitMQ's main signing key
curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" | sudo gpg --dearmor | sudo tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null
## Community mirror of Cloudsmith: modern Erlang repository
curl -1sLf https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-erlang.E495BB49CC4BBE5B.key | sudo gpg --dearmor | sudo tee /usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg > /dev/null
## Community mirror of Cloudsmith: RabbitMQ repository
curl -1sLf https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-server.9F4587F226208342.key | sudo gpg --dearmor | sudo tee /usr/share/keyrings/rabbitmq.9F4587F226208342.gpg > /dev/null

## Add apt repositories maintained by Team RabbitMQ
sudo tee /etc/apt/sources.list.d/rabbitmq.list <<EOF
## Provides modern Erlang/OTP releases
##
deb [arch=amd64 signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa1.rabbitmq.com/rabbitmq/rabbitmq-erlang/deb/debian bookworm main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa1.rabbitmq.com/rabbitmq/rabbitmq-erlang/deb/debian bookworm main

# another mirror for redundancy
deb [arch=amd64 signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa2.rabbitmq.com/rabbitmq/rabbitmq-erlang/deb/debian bookworm main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.E495BB49CC4BBE5B.gpg] https://ppa2.rabbitmq.com/rabbitmq/rabbitmq-erlang/deb/debian bookworm main

## Provides RabbitMQ
##
deb [arch=amd64 signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa1.rabbitmq.com/rabbitmq/rabbitmq-server/deb/debian bookworm main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa1.rabbitmq.com/rabbitmq/rabbitmq-server/deb/debian bookworm main

# another mirror for redundancy
deb [arch=amd64 signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa2.rabbitmq.com/rabbitmq/rabbitmq-server/deb/debian bookworm main
deb-src [signed-by=/usr/share/keyrings/rabbitmq.9F4587F226208342.gpg] https://ppa2.rabbitmq.com/rabbitmq/rabbitmq-server/deb/debian bookworm main
EOF

## Update package indices
sudo apt update -y

## Install Erlang packages
sudo apt install -y erlang-base \
                        erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
                        erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
                        erlang-runtime-tools erlang-snmp erlang-ssl \
                        erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl

## Install rabbitmq-server and its dependencies
sudo apt install rabbitmq-server -y --fix-missing
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


## MariaDB

_n6_ uses two SQL databases - event database and _Auth DB_.
The event database primarily stores processed information about network events and possible
security incidents, also their relation to organizations linked to clients.
The _Auth DB_ database is used for client authorization. It stores clients' permissions
and information about allowed resources (allowed API endpoints, allowed _subsources_).

The required version of MariaDB is 10.3 which is not supported by Debian 12 using a package manager.
One of the installation methods is to use MariaDB Binary Tarballs.

To install MariaDB from Generic Binaries on Unix/Linux, download the appropriate binary version.
Go to _https://mariadb.org/download_, select and download MariaDB Server 10.3.x version.

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
$ sudo wget https://archive.mariadb.org/mariadb-10.3.22/bintar-linux-systemd-x86_64/mariadb-10.3.22-linux-systemd-x86_64.tar.gz
$ sudo tar -zxvpf mariadb-10.3.22-linux-systemd-x86_64.tar.gz -C /usr/local/mysql/ --strip-components 1
$ sudo rm mariadb-10.3.22-linux-systemd-x86_64.tar.gz 
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
Create (if it does not already exist) an empty `/etc/mysql/my.cnf` file and fill it with configuration content like below:

```bash
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
$ sudo /usr/local/mysql/scripts/mysql_install_db --user=mysql
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
$ sudo echo "export PATH=${PATH}:/usr/local/mysql/bin" >> ~/.bashrc
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

### Arrangements related to Apache

Add `dataman` to the `www-data` group, make the necessary directories,
and set appropriate permissions:

```bash
$ sudo /usr/sbin/usermod -a -G dataman www-data
$ sudo mkdir -p /home/dataman/env_py3k/.python-eggs
$ sudo chown -R dataman:www-data /home/dataman/env_py3k
$ sudo chmod -R 775 /home/dataman/env_py3k/.python-eggs
$ sudo chmod -R 775 /home/dataman/ /var/www /etc/ssh/ /etc/apache2/sites-available/
$ sudo chown -R dataman:dataman /home/dataman/ /var/www /etc/ssh/ \
        /etc/apache2/sites-available/
```

## (Optionally) MongoDB

_n6_ uses MongoDB as archival database. Events gathered by collectors will
be stored in MongoDB and can be restored in case of errors.

Installation steps below are based on
[Install MongoDB Community Edition on Debian](https://docs.mongodb.com/manual/tutorial/install-mongodb-on-debian/)
solution.

Install `libssl1.1` and `libssl1.1-dev`

```bash
$ wget http://ftp.pl.debian.org/debian/pool/main/o/openssl/libssl1.1_1.1.1w-0+deb11u1_amd64.deb
$ wget http://ftp.pl.debian.org/debian/pool/main/o/openssl/libssl-dev_1.1.1w-0+deb11u1_amd64.deb
$ sudo dpkg -i libssl1.1_1.1.1w-0+deb11u1_amd64.deb
$ sudo dpkg -i libssl-dev_1.1.1w-0+deb11u1_amd64.deb
$ rm -i libssl1.1_1.1.1w-0+deb11u1_amd64.deb
$ rm -i libssl-dev_1.1.1w-0+deb11u1_amd64.deb
```

To install MongoDB, do the following (as `root`):

```bash
$ wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | apt-key add - &&
  echo "deb http://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.2 multiverse" | tee /etc/apt/sources.list.d/mongodb-org.list
$ apt update && apt install -y mongodb-org
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
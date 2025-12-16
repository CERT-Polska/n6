<style>
  code.language-bash::before{
    content: "$ ";
  }
  code.language-bashroot::before{
    content: "# ";
  }
</style>


# System Preparation

The *n6* system requires a contemporary _**Linux**_-based operating
system, such as [*Debian GNU/Linux*](https://www.debian.org/).

!!! important

    This guide assumes that you have installed [_**Debian 12**_
    (*Bookworm*)](https://www.debian.org/releases/bookworm/).

    Installation of other required software is described in respective
    sections of this chapter.

!!! note

    This guide assumes, for simplicity of description, that all components
    are installed on the same machine/system. This is not a requirement,
    just one of possible approaches.

Third-party software the *n6* system depends on includes:

* [*RabbitMQ*](https://www.rabbitmq.com/) (an AMQP message broker),
* [*MariaDB*](https://mariadb.org/) (a SQL database server) with the
  [*RocksDB*](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks)
  engine enabled.

You also need:

* a WSGI-compatible web server (for the purposes of this guide, it is
  [*Apache*](https://httpd.apache.org/)) -- to set up and run any of
  the *web* components of *n6* (*Portal*, *REST API*, *Admin Panel*);
* the necessary JavaScript toolchain (including
  [*Node.js*](https://nodejs.org/en) and
  [*Yarn*](https://yarnpkg.com/)...) -- to build the frontend (GUI) part
  of the *Portal* component.

!!! important

    Internet access is required during the entire installation process.


## Basic Dependencies and Tools

First, as the `root` OS user (superuser), install a bunch of necessary
Debian packages:

```bashroot
apt update \
  && apt upgrade -y \
  && apt install -y \
      build-essential \
      curl \
      gnupg \
      default-libmysqlclient-dev \
      git \
      libgeoip1 \
      python3.11 \
      python3.11-dev \
      python3.11-venv \
      ssh \
      sudo \
      supervisor \
      swig \
      wget \
  && apt clean
```


## User, Code and Auxiliary Stuff

A separate OS user is needed. For the purposes of this guide, let the
username be `dataman`.

### User `dataman`

Still as the `root` OS user (superuser), create the `dataman` user
(being a member of the `dataman`, `sudo` and `www-data` groups):

```bashroot
/usr/sbin/groupadd dataman \
  && /usr/sbin/useradd -rm \
      -d /home/dataman \
      -s /bin/bash \
      -p '' \
      -g dataman \
      -G sudo,www-data \
      dataman
```

...and adjust access permissions on the new user's home directory:

```bashroot
chown dataman:www-data /home/dataman \
  && chmod 710 /home/dataman
```

Now, switch to that user's shell:

```bashroot
su - dataman
```

!!! important

    The rest of the commands this guide includes, shall be executed from the
    `dataman` user's shell (the above **`su - dataman`** command was the
    last one executed directly as `root`).

Already within the `dataman` user's shell, explicitly set the current
*umask* mode to a relatively safe, yet convenient, standard value (just
in case):

```bash
umask 0022
```


### Source Code of *n6*

Clone the *n6* source code repository into the `n6` subdirectory of the
`dataman`'s home directory:

```bash
git clone https://github.com/CERT-Polska/n6.git ~/n6
```


### Example Certificates

For convenience in later steps, copy the example X.509 certificates/keys
shipped with the *n6* source code into the `certs` subdirectory of the
`dataman`'s home directory:

```bash
sudo cp -rf /home/dataman/n6/etc/ssl/generated_certs/ /home/dataman/certs
```

!!! warning

    Those *example certificate/key files* should **never** be used in
    production!


### Necessary Files/Directories

Also, you need to create certain directories...

For configuration of the *n6 pipeline* components and *n6 Admin Panel*:

```bash
mkdir -m 710 .n6 \
  && chown dataman:www-data .n6
```

(Actual configuration files are [to be placed there
later...](config.md#n6-pipeline-components))

For local state stored by some of the *n6 pipeline* components:

```bash
mkdir -m 700 .n6state
```

For some *n6* components' auxiliary caches:

```bash
mkdir -m 755 -p .cache \
  && mkdir -m 710 .cache/n6 \
  && chown dataman:www-data .cache/n6
```

And for all *n6* components' logs:

```bash
mkdir -m 770 logs \
  && chown dataman:www-data logs
```

Then, create the actual log file:

```bash
touch logs/log_n6_all \
  && chown dataman:www-data logs/log_n6_all \
  && chmod 660 logs/log_n6_all
```


## RabbitMQ

*RabbitMQ* is an open source message broker software that implements
Advanced Message Queuing Protocol (AMQP). The broker is responsible for
communication between most of the *n6 pipeline* components.

### Installing and Starting

Install the RabbitMQ broker:

```bash
sudo apt install -y rabbitmq-server
```

...and make sure it is started: 

```bash
sudo service rabbitmq-server restart
```

You can always check whether the `rabbitmq-server` service is running, by
executing the command:

```bash
sudo service rabbitmq-server status
```

### Enabling Plugins

To enable certain necessary (or potentially necessary) plugins, execute:

```bash
sudo /usr/sbin/rabbitmq-plugins enable \
    rabbitmq_management \
    rabbitmq_management_agent \
    rabbitmq_auth_mechanism_ssl \
    rabbitmq_federation \
    rabbitmq_federation_management \
    rabbitmq_shovel \
    rabbitmq_shovel_management
```

The command's output should include:

```
The following plugins have been configured:
  rabbitmq_auth_mechanism_ssl
  rabbitmq_federation
  ...
Applying plugin configuration to rabbit@...
The following plugins have been enabled:
  rabbitmq_auth_mechanism_ssl
  rabbitmq_federation
  ...
started 8 plugins.
```

### Adjusting Configuration

Copy the *n6*'s example RabbitMQ configuration file into its target
location:

```bash
sudo cp -a /home/dataman/n6/etc/rabbitmq/conf/rabbitmq.conf /etc/rabbitmq/
```

Then edit the `/etc/rabbitmq/rabbitmq.conf` file -- to set the three
SSL-certificate-files-related options as follows:

```
ssl_options.cacertfile = /etc/rabbitmq/n6-certs/cacert.pem
ssl_options.certfile   = /etc/rabbitmq/n6-certs/cert.pem
ssl_options.keyfile    = /etc/rabbitmq/n6-certs/key.pem
```

(For the purposes of this guide, other options can be left intact...)

Do not forget to set the appropriate permissions regarding that
configuration file:

```bash
sudo chmod 644 /etc/rabbitmq/rabbitmq.conf \
  && sudo chown root:root /etc/rabbitmq/rabbitmq.conf
```

!!! warning

    Keep in mind that the RabbitMQ configuration prepared this way contains
    various elements that should **never** be used in production, e.g. the
    possibility to authenticate (and be authorized to access any resources)
    using the `guest` user/password...

    It is also worth reminding that production services, including message
    brokers, should **not** accept network connections which are not properly
    protected with SSL (TLS).

Also, create a RabbitMQ configuration subdirectory for
SSL-certificate-related files:

```bash
sudo mkdir -m 710 /etc/rabbitmq/n6-certs \
  && sudo chown root:rabbitmq /etc/rabbitmq/n6-certs
```

And copy the *n6*'s example certificate and key files into that directory:

```bash
sudo cp \
  /home/dataman/certs/n6-CA/cacert.pem \
  /home/dataman/certs/cert.pem \
  /home/dataman/certs/key.pem \
  /etc/rabbitmq/n6-certs/
```

!!! warning

    Those *example certificate/key files* should **never** be used in
    production!

Finally, restart the `rabbitmq-server` service:

```bash
sudo service rabbitmq-server restart
```

Now you should be able to sign in, with a web browser, to the management
GUI of your RabbitMQ instance at
[https://localhost:15671](https://localhost:15671) -- using  the default
*guest* credentials (username: `guest`, password: `guest`).

!!! note

    Because of the use of the aforementioned *insecure example certificate*,
    any modern web browser is expected to warn you that the connection is
    not secure. **Before the browser agrees to display the site, you may
    need to confirm that you accept the risk.** Also, for your convenience,
    you may want to add in your browser a permanent security exception for
    this site.


## MariaDB

*MariaDB* is an open source SQL database server software.

*n6* uses two SQL databases for which a MariaDB server is needed: *Event
DB* (which makes use of the *RocksDB* engine) and *Auth DB* (which makes
use of the standard *InnoDB* engine). The purpose of each will be
discussed [later](config.md#initializing-n6s-databases) in this guide...

### Installing and Starting

Install the necessary MariaDB stuff:

```bash
sudo apt install -y mariadb-client mariadb-server mariadb-plugin-rocksdb
```

...and make sure the MariaDB server is started:

```bash
sudo service mariadb restart
```

You can always check whether the `mariadb` service is running, by executing
the command:

```bash
sudo service mariadb status
```

### Checking the Stuff

Make sure you have access to the database:

```bash
sudo mysql -u root
```

In the `mysql` command's prompt, type:

```
SHOW plugins;
```

Many lines will be printed... One of them should start with:

```
| ROCKSDB                       | ACTIVE   | STORAGE ENGINE     |
```

(its presence confirms that the aforementioned *RocksDB* database engine
is active).

### Enabling Access by Password

Still at the `mysql` client's prompt, make it possible to authenticate
the ``` `root`@`localhost` ``` account with the `password` password
(also keeping enabled, just for the `root` OS user, the passwordless
Unix-socket-based authentication mechanism):

```
GRANT ALL PRIVILEGES ON *.*
  TO `root`@`localhost`
  IDENTIFIED VIA mysql_native_password
  USING '*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19'
  OR unix_socket
  WITH GRANT OPTION;
```

!!! warning

    Obviously, silly passwords like `password` should **never** be used in
    production!

    Furthermore, in production, *n6* components should **not** use the
    privileged `root` database account (instead, separate database account(s)
    with appropriately restricted permissions would need to be created...).

    It is also worth reminding that production services, including database
    servers, should **not** accept network connections which are not properly
    protected with SSL (TLS).

Finally, exit the `mysql` client by typing:

```
exit;
```


## Apache

**(just for *web* components of *n6*)**

A WSGI-compatible web (HTTP) server software is needed to run such
services as *n6 REST API*, *n6 Portal API* and *n6 Admin Panel*.

*Apache* is an open source web server which (together with its module
`mod_wsgi`) is to be used for the purposes of this guide...

### Installing and Starting

Install the Apache server:

```bash
sudo apt install -y apache2 libapache2-mod-wsgi-py3
```

...and make sure it is started:

```bash
sudo service apache2 restart
```

!!! note

    A warning similar to the following may be printed:

    `Could not reliably determine the server's fully qualified domain name,
    ... Set the 'ServerName' directive globally to suppress this message`.

    It can be ignored for a *non-production* installation.

You can always check whether the `apache2` service is running, by executing
the command:

```bash
sudo service apache2 status
```

### Enabling Modules

Now, enable some necessary Apache modules...

First, the `ssl` module:

```bash
sudo /usr/sbin/a2enmod ssl
```

The command's output should include:

```
Enabling module socache_shmcb.
Enabling module ssl.
```

Then, the `rewrite` module:

```bash
sudo /usr/sbin/a2enmod rewrite
```

The command's output should include:

```
Enabling module rewrite.
```

Also, ensure the `wsgi` module is enabled (typically, it already is):

```bash
sudo /usr/sbin/a2enmod wsgi
```

The command's output is (therefore) expected to be:

```
Module wsgi already enabled
```

Now, restart the `apache2` service, activating the newly enabled modules: 

```bash
sudo service apache2 restart
```


## JavaScript Toolchain

**(just for the *n6 Portal* web component)**

To be able to build the frontend (GUI) of *n6 Portal*, you need to
install certain JavaScript-related software (in particular, *Node.js*
and *Yarn*...).

To do so, first ensure that the Debian repository keyrings directory
exists:

```bash
sudo mkdir -p /etc/apt/keyrings
```

Then download the Node.js repository's GPG key and save it in that directory:

```bash
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
```

Add the Node.js repository to the list of Debian repositories...

```bash
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg]" \
     "https://deb.nodesource.com/node_22.x nodistro main" \
  | sudo tee /etc/apt/sources.list.d/nodesource.list
```

...and appropriately pin the `nodejs` Debian package (to work around the problem described at
[https://github.com/nodesource/distributions/issues/1601](https://github.com/nodesource/distributions/issues/1601)):

```bash
printf "Package: nodejs\nPin: origin deb.nodesource.com\nPin-Priority: 1001\n" \
  | sudo tee -a /etc/apt/preferences.d/preferences
```

Update the *apt*'s package information:

```bash
sudo apt update
```

Finally, install the necessary stuff:

```bash
sudo apt install -y nodejs \
  && sudo npm install --global npm@9 \
  && sudo npm install --global yarn
```


## MongoDB (not anymore)

(*In previous versions of the guide we described here how to install
MongoDB 4.2, required solely by the `n6archiveraw` optional component,
which is no longer recommended to be used*...)

!!! info "Removing deprecated component"

    The `n6archiveraw` component, which makes use of an old (no longer
    supported) version of MongoDB, is deprecated. We recommend ignoring that
    old component.

    Soon, in a future version of *n6*, `n6archiveraw` will be replaced with
    a brand new component: `n6archiver`. The new component will make use of
    a data storage technology other than MongoDB.

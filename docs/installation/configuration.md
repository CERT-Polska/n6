# Configuration of _n6_ components

**TBD: the following description needs an update regarding the
stuff that now works under Python 3.9; in particular, the current
implementation of the *n6* basic data pipeline now resides in
`N6DataPipeline`, *not* in `N6Core` (where the legacy Python-2.7
stuff resides).**


## Generating pipeline components' configuration files

To create configuration files required for the _n6_ pipeline (`N6Core`)
components to work, run the command:

```bash
(env)$ n6config
Copy sample configuration files to the system? [Y/n]
Y
No write access to '/etc/n6'. Write to '/home/dataman/.n6' instead? [Y/n]
Y
Success.
```

The configuration files should have been created in `/home/dataman/.n6`.

```bash
(env)$ ls /home/dataman/.n6/
00_global.conf  05_enrich.conf  07_comparator.conf  09_manage.conf
23_filter.conf  70_badips.conf  70_greensnow.conf  70_packetmail.conf
70_zone_h.conf  02_archiveraw.conf  07_aggregator.conf  09_auth_db.conf
21_recorder.conf  70_abuse_ch.conf  70_dns_bh.conf  70_misp.conf  70_spam404.conf
logging.conf
```

## Logging

Let us adjust logging configuration by editing `/home/dataman/.n6/logging.conf`

Example configuration with the _root_ logger and handlers: _syslog_ (writes to Syslog) and _stream_
(displays log as an output of a process):

```ini
[loggers]
keys = root

[handlers]
keys = syslog, stream

[formatters]
keys = n6_syslog_handler, standard

[logger_root]
level = INFO
handlers = syslog, stream

[handler_stream]
class = StreamHandler
level = INFO
formatter = standard
args = (sys.stdout,)

[handler_syslog]
class = n6lib.log_helpers.N6SysLogHandler
level = WARNING
formatter = n6_syslog_handler
args = ('/dev/log',)

[formatter_standard]
format = n6: %(levelname) -10s %(asctime)s %(name) -25s in %(funcName)s() (#%(lineno)d): %(message)s

[formatter_n6_syslog_handler]
format = n6: %(levelname) -10s %(asctime)s %(script_basename)s, %(name)s in %(funcName)s() (#%(lineno)d): %(message)s
class = n6lib.log_helpers.NoTracebackCutFormatter
```

With the configuration above, _syslog_ handler is set to _WARNING_, _stream_ handler is set
to _INFO_, and the logger overall is set to _INFO_ logging level. You can change logging levels
for each handler separately or for the logger globally.

## Enricher

The Enricher uses a DNS resolver to enrich data by adding IP addresses converted from FQDNs,
so you need to provide proper values for config options: _dnshost_ (hostname of a DNS resolver),
_dnsport_ (port number of the resolver) in the `~/.n6/05_enrich.conf` file.

If you have access to GeoIP databases (_GeoLite2-ASN_ or/and _GeoLite2-City_) and want Enricher
to add ASN or/and CC to acquired addresses, you should provide value for config option _geoippath_
and one or both of _asndatabasefilename_ and _asndatabasefilename_.

If you do not want Enricher to enrich some IP addresses, you can blacklist them by appending
to a list in the not required option _excluded_ips_. Example Enricher's configuration:

```ini
[enrich]
dnshost=8.8.8.8
dnsport=53
geoippath=/usr/share/GeoIP ; a directory with GeoIP database files, if provided
asndatabasefilename=GeoLite2-ASN.mmdb ; optional GeoLite2-ASN database file
citydatabasefilename=GeoLite2-City.mmdb ; optional GeoLite2-City database file
excluded_ips=0.0.0.0, 127.0.0.1 ; optional blacklist of IP addresses
```

Note that you can download GeoIP database files from:
[https://dev.maxmind.com/geoip/geoip2/geolite2/](https://dev.maxmind.com/geoip/geoip2/geolite2/)

## RabbitMQ

_n6_ configuration for RabbitMQ lies in section `rabbitmq`, in the file:  
`/home/dataman/.n6/00_global.conf`

Let us change option `port=5671` to `port=5672` in the section.

Now, let us try to run one of _n6_ parsers!

```bash
(env)$ n6parser_spam404
n6: INFO       2020-01-16 12:31:17,313 UTC n6lib.log_helpers         in configure_logging() (#133): logging configuration loaded from '/home/dataman/.n6/logging.conf'
n6: INFO       2020-01-16 12:31:17,316 UTC n6lib.config              in _load_n6_config_files() (#1042): Config files read properly: "/home/dataman/.n6/00_global.conf", "/home/dataman/.n6/02_archiveraw.conf", "/home/dataman/.n6/05_enrich.conf", "/home/dataman/.n6/07_aggregator.conf", "/home/dataman/.n6/07_comparator.conf", "/home/dataman/.n6/09_auth_db.conf", "/home/dataman/.n6/09_manage.conf", "/home/dataman/.n6/21_recorder.conf", "/home/dataman/.n6/23_filter.conf", "/home/dataman/.n6/70_abuse_ch.conf", "/home/dataman/.n6/70_badips.conf", "/home/dataman/.n6/70_dns_bh.conf", "/home/dataman/.n6/70_greensnow.conf", "/home/dataman/.n6/70_misp.conf", "/home/dataman/.n6/70_packetmail.conf", "/home/dataman/.n6/70_spam404.conf", "/home/dataman/.n6/70_zone_h.conf"
n6: INFO       2020-01-16 12:31:17,319 UTC n6.base.queue             in connect() (#459): Connecting to localhost
n6: INFO       2020-01-16 12:31:17,320 UTC pika.adapters.base_connection in _create_and_connect_to_socket() (#212): Connecting to ::1:5672
n6: INFO       2020-01-16 12:31:17,324 UTC n6.base.queue             in on_connection_open() (#492): Connection opened
n6: INFO       2020-01-16 12:31:17,343 UTC n6.base.queue             in open_channels() (#537): Creating new channels
```

Notice the last lines of the log. The parser created channels, so it means that the _n6_ component
is connected with the RabbitMQ server. Log in to RabbitMQ's management graphical interface by `rabbitmq-server` with browser
going to `http://localhost:15672` in web browser and check the tab **queues**. There should be a new entry:

```text
spam404-com.scam-list
```

You can close the parser with `CTRL + c`. It will gracefully close the connection and exit.

## SQL databases (MariaDB)

MySQL setup configuration can be found in `/etc/mysql/my.cnf`. _n6_ provides its own configuration
in `n6/etc/mysql/conf.d/mariadb.cnf`. Adjust this configuration as a root and restart the _mariadb_
process:

```bash
# cp /home/dataman/n6/etc/mysql/conf.d/mariadb.cnf /etc/mysql/my.cnf
# systemctl restart mariadb
```

Remove plugins from user:

```bash
# mysql -p -u root -e 'update mysql.user set plugin=" " where User="root";flush privileges;'
```

Now, it's time to adjust relevant _n6_ configuration files...

### Event DB

As the `dataman` user, edit `/home/dataman/.n6/21_recorder.conf`, section `recorder`. Primarily,
set a proper database URI - SQL _event_ database (URI should include username, password,
hostname and database name):

```ini
[recorder]
uri = mysql://root:yourMysqlPassword@localhost/n6
echo = 0
wait_timeout = 28800
```

SQL files placed under `n6/etc/mysql/initdb` will create tables `events` and `client_to_event`
in database `n6` (tables used mainly for event storage).

```bash
$ mysql -p -u root < /home/dataman/n6/etc/mysql/initdb/1_create_tables.sql
$ mysql -p -u root < /home/dataman/n6/etc/mysql/initdb/2_create_indexes.sql
```

### Auth DB

_Auth DB_ database is used for authentication and authorization.

First, edit (as the `dataman` user) the `/home/dataman/.n6/09_auth_db.conf`
file, section `auth_db`:

```ini
[auth_db]
url = mysql://root:yourMysqlPassword@localhost/auth_db
```

(**Note**: here it is `url`, not `uri` as above.)

Tables for authentication should be created using _n6_ script `n6create_and_initialize_auth_db`:

```bash
(env)$ n6create_and_initialize_auth_db -D -y
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

**Warning: the `-D` flag makes the script drop the target database first;
and the `-y` flag suppress any confirmation prompts!**

(See also: `$ n6create_and_initialize_auth_db --help`.)

In the example below, we will add some example data to the _AuthDB_, including a user and
organization, which should match the subject of the client certificate, that will be used
to authenticate against _n6 REST API_.  
By using flags `-i -t -s` the new organization will have access to _inside_, _threats_
and _search_ access zones. (Additionally, you can specify, e.g., the `-F` flag to give the organization the _full access_ rights. See also: `$ n6populate_auth_db --help`.)

```bash
(env)$ n6populate_auth_db -i -t -s example.com login@example.com
* The 'n6populate_auth_db' script started.
* Inserting records...
Source "abuse-ch.spyeye-doms"
Source "abuse-ch.spyeye-ips"
Source "abuse-ch.zeus-doms"
[...]
Subsource "general access to packetmail-net.others-list"
Subsource "general access to spam404-com.scam-list"
Subsource "general access to zoneh.rss"
Org "example.com"
User "login@example.com"
* The 'n6populate_auth_db' script exits gracefully.
```

**IMPORTANT - Positional arguments of the _n6populate_auth_db_ script:**

- ORG_ID (here: `example.com`) must match the subject's `O` field in the X.509 client
  certificate used for certificate-based authentication against _n6 REST API_ and _n6 Portal_.
- USER_LOGIN (here: `login@example.com`) must match the subject's `CN` field in the
  X.509 client certificate used for certificate-based authentication against _n6 REST API_
  and _n6 Portal_.

## Archive DB (MongoDB)

To start with, make sure that `mongod` process is running:

```bash
$ systemctl status mongod
```

Now, run `mongo`:

```bash
$ mongo
```

In order to create users and database for _n6_ data, copy-paste content of
the `n6/etc/mongo/initdb/create_users.js` file, like below:

```sql
use n6;
<pasted content of the file>
```

**Adjust MongoDB configuration in** `/etc/mongod.conf`:

```yaml
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: false

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

net:
  port: 27017
  bindIp: 0.0.0.0

security:
  authorization: enabled
```

Restart the MongoDB server. To run `mongod` during system startup you need to create
a symlink to the \*.service\_ file for `systemd`:

```bash
$ systemctl enable mongod
Created symlink /etc/systemd/system/multi-user.target.wants/mongod.service → /lib/systemd/system/mongod.service.
$ systemctl restart mongod
```

Check the status of the `mongod` service:

```bash
$ systemctl status mongod
● mongod.service - MongoDB Database Server
   Loaded: loaded (/lib/systemd/system/mongod.service; enabled; vendor preset:
   Active: active (running) since Thu 2019-09-05 15:41:50 CEST; 1s ago
     Docs: https://docs.mongodb.org/manual
 Main PID: 12803 (mongod)
   Memory: 40.0M
   CGroup: /system.slice/mongod.service
           └─12803 /usr/bin/mongod --config /etc/mongod.conf
```

**Adjust the _n6 Archive Raw_ configuration in** `/home/dataman/.n6/02_archiveraw.conf`

```ini
[archiveraw]
mongohost = 127.0.0.1
mongoport = 27017
mongodb = n6
time_sleep_between_try_connect=5               ; time sleep (sec) between trying to reconnect
count_try_connection=1000
uri = mongodb://admin:password@%(mongohost)s:%(mongoport)s/?authSource=n6&authMechanism=SCRAM-SHA-1
```

To test the _n6 Archive Raw_ component, _rabbitmq-server_ and _mongod_ services have to be
configured and running. Then run:

```bash
(env)$ n6archiveraw
```

The `n6archiveraw` process stops on `SIGINT` (`CTRL + c`) or `SIGTERM` signal. After a few seconds,
all messages from the `dba` queue should be consumed by `n6archiveraw`.

Now, as a `dataman` user, run some n6 collector (for example the _AbuseChSSLBlacklistCollector_):

```bash
(env)$ n6collector_abusechsslblacklist
```

A collector should collect data, send gathered data to the message broker (RabbitMQ) and quit.
If you look into the RabbitMQ Management GUI, there should appear one or more messages in
the _n6 Archive Raw_ `dba` inner queue.
The _n6 Archive Raw_ component consumes messages from its inner queue and archives them
in the MongoDB database.

There should be logs similar to examples below:

```bash
n6: INFO 2020-01-16 16:53:21,973 UTC pika.adapters.base_connection in _create_and_connect_to_socket() (#212): Connecting to ::1:5672
n6: INFO 2020-01-16 16:53:21,976 UTC n6.base.queue             in on_connection_open() (#492): Connection opened
n6: INFO 2020-01-16 16:53:21,976 UTC n6.base.queue             in open_channels() (#537): Creating new channels
n6: INFO 2020-01-16 16:53:22,436 UTC n6.archiver.archive_raw   in create_indexes() (#366): Create indexes: 'rid' on collection: u'abuse-ch.ssl-blacklist.201902.files'
n6: INFO 2020-01-16 16:53:22,534 UTC n6.archiver.archive_raw   in create_indexes() (#366): Create indexes: 'md5' on collection: u'abuse-ch.ssl-blacklist.201902.files'
```

Check the MongoDB database:

```bash
$ mongo -u admin -p password --authenticationDatabase n6
> use n6;
> db.getCollectionNames()
[
    "abuse-ch.ssl-blacklist.201902.chunks",
    "abuse-ch.ssl-blacklist.201902.files",
]
> db.getCollection('abuse-ch.ssl-blacklist.201902.files').find()
{ "_id" : ObjectId("5e2095026e95522c7f86929c"), "received" : ISODate("2020-01-16T16:47:08Z"), "contentType" : "text/csv", "chunkSize" : 261120, "length" : 219846, "uploadDate" : ISODate("2020-01-16T16:53:22.655Z"), "http_last_modified" : "2020-01-11 14:00:00", "rid" : "8173d72f6d69142ceaa9cfa9ae908506", "md5" : "3a22aff3d9a3099f509d4cec45fe72ea" }
```

If you see similar output like the example above, then `n6archiveraw`, `mongod`, `rabbitmq-server`
services work as expected!

### Troubleshooting: [ERROR] Failed to unlink socket file /tmp/mongodb-27017

There might be an issue with starting the `mongod` process.
Check the `/var/log/mongodb/mongod.log` file for the following error messages:

```bash
2017-08-24T03:57:21.289-0400 I CONTROL  [initandlisten] options: { config: "/etc/mongod.conf", net: { bindIp: "127.0.0.1,192.168.x.x" }, storage: { dbPath: "/var/lib/mongodb3" }, systemLog: { destination: "file", logAppend: true, path: "/var/log/mongodb/mongod.log" } }
2017-08-24T03:57:21.311-0400 E NETWORK  [initandlisten] Failed to unlink socket file /tmp/mongodb-27017.sock errno:1 Operation not permitted
2017-08-24T03:57:21.311-0400 I -        [initandlisten] Fatal Assertion 28578
2017-08-24T03:57:21.311-0400 I -        [initandlisten]
```

See more at [mkyong issue](https://mkyong.com/mongodb/mongodb-failed-to-unlink-socket-file-tmpmongodb-27017/)

Quick way to resolve the issue:

```bash
$ rm -rf /tmp/mongodb-27017.sock
```

```bash
$ service mongod start
```

## Apache2

Add `dataman` to the `www-data` group, make the necessary directories,
and set appropriate permissions:

```bash
$ /usr/sbin/usermod -a -G dataman www-data
$ mkdir /home/dataman/env/.python-eggs
$ chown dataman:www-data /home/dataman/env/.python-eggs
$ chmod 775 /home/dataman/env/.python-eggs
$ chown -R www-data:www-data /etc/apache2/sites-available/
```

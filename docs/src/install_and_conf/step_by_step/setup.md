In this section we will setup whole *n6* application. If you wish to use specific parts of *n6* you should check:

- [API](web_components_config.md#n6-rest-api) for *N6 REST API*.
- [Portal](web_components_config.md#n6-portal) for  *N6 Portal*.
- [N6 DataPipelines](pipeline_config.md) for *N6 DataPipelines*.

## Setting up event & auth databases (MariaDB)

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

!!! note

    Here it is `url`, not `uri` as earlier.

Tables for authentication should be created using _n6_ script `n6create_and_initialize_auth_db`:

```bash
(env_py3k)$ n6create_and_initialize_auth_db -D -y
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

In the example below, we will add some example data to the _AuthDB_, including a user and organization.  
By using flags `-i -t -s` the new organization will have access to _inside_, _threats_
and _search_ access zones. (Additionally, you can specify, e.g., the `-F` flag to give the organization the _full access_ rights. See also: `$ n6populate_auth_db --help`.)
Also flag `-p` will ask you for the password.

```bash
(env_py3k)$ n6populate_auth_db -i -t -s -p example.com login@example.com
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

## Apache2 ServerName

!!!Note
    It is advised to change the default secrets in `/home/dataman/n6/web/conf/portal.ini`.

Add the `ServerName` option in `/home/dataman/n6/etc/apache2/sites-available/n6-api.conf` with your server's name
as its value, so a part of configuration looks like the one below:

```bash
<VirtualHost *:4443>
    ServerAdmin admin@localhost
    ServerName localhost  # add this line
```
Copy (as root) the Apache2 config files from `home/n6/etc/apache2/sites-available/*.conf` files into `/etc/apache2/sites-available/`:

```bash
$ cp /home/dataman/n6/etc/apache2/sites-available/*.conf /etc/apache2/sites-available/
```

Also set `ServerName` (as root) in `etc/apache2/apache2.conf`:

```bash
$ echo 'ServerName localhost' >> /etc/apache2/apache2.conf
```

## Setting database urls

Set up database connection addresses in `/home/dataman/n6/etc/web/conf/api.ini` (_Pyramid_
framework configuration):

```ini
sqlalchemy.url = mysql://root:password@localhost/n6
auth_db.url = mysql://root:password@localhost/auth_db
```
Set up connections to the databases in configuration file `/home/dataman/n6/etc/web/conf/portal.ini`:

```ini
sqlalchemy.url = mysql://root:password@localhost/n6
auth_db.url = mysql://root:password@localhost/auth_db
```

Also set up connection to auth db database in configruation file `/home/dataman/.n6/admin_panel.conf`

```ini
auth_db.url = mysql://root:password@localhost/auth_db
```

## Deploy N6 Portal

Install dependencies and build GUI application:

```bash
(env_py3k)$ cd /home/dataman/n6/N6Portal/react_app
(env_py3k)$ yarn
(env_py3k)$ npm_config_yes=true npx yarn-audit-fix
(env_py3k)$ yarn build
```

## Enabling websites

Enable the websites:

```bash
$ sudo a2enmod wsgi && \
    sudo a2enmod ssl && \
    sudo a2enmod rewrite && \
    sudo a2ensite 000-default && \
    sudo a2ensite n6-api && \
    sudo a2ensite n6-portal && \
    sudo a2ensite n6-adminpanel
$ systemctl restart apache2
```

### Available ports:

  - 80 -- redirects to 443 (to use HTTPS)
  - 443 -- _n6_ Portal GUI + _n6_ Portal API (`/api`)
  - 4443 -- _n6_ REST API
  - 4444 -- _n6_ Admin Panel
  - 15671 -- RabbitMQ Management

You can log into account created with `n6populate_auth_db` into `https://localhost/`
or use `Admin Panel` to add new user.
# Configuration of _n6_ Web Components

!!! note

    The following examples assume the home directory path is `/home/dataman`
    and the project directory path is `/home/dataman/n6`.

!!! Note

    To complete any of the steps described below you need to have:

    * the system prepared (see: [System Preparation](system.md), except that here you need *neither* RabbitMQ *nor* MongoDB)
    * the relevant *n6* component(s) installed (see: [Installation of *n6* Components](installation.md))
    * the relevant SQL databases prepared (see: [SQL databases...](pipeline_config.md#sql-databases-mariadb))
    * necessary certificates generated (see: [Certificates](certificates.md))

## _n6 REST API_

Set up database connection addresses in `/home/dataman/n6/etc/web/conf/api.ini` (_Pyramid_
framework configuration):

```ini
sqlalchemy.url = mysql://root:password@localhost/n6
auth_db.url = mysql://root:password@localhost/auth_db
```

Copy (as root) the Apache2 config from `/home/dataman/n6/etc/apache2/sites-available/n6-api.conf`
to `/etc/apache2/sites-available/`.

```bash
$ cp /home/dataman/n6/etc/apache2/sites-available/n6-api.conf /etc/apache2/sites-available/
```

Add the `ServerName` option in `/etc/apache2/sites-available/n6-api.conf` with your server's name
as its value, so a part of configuration looks like the one below:

```bash
<VirtualHost *:4443>
    ServerAdmin admin@localhost
    ServerName localhost  # add this line
```

Also set the `ServerName` in `/etc/apache2/apache2.conf`:

```bash
$ sudo echo 'ServerName localhost' >> /etc/apache2/apache2.conf
```

Enable the website:

```bash
$ sudo a2ensite n6-api
$ systemctl restart apache2
```

### Querying the API

```bash
(env_py3k)$ cd ~/certs
(env_py3k)$ curl --cert cert.pem --key key.pem -k 'https://localhost:4443/search/events.json?time.min=2015-01-01T00:00:00'
[

]
```

This response means the _event_ database is empty.

### _n6 REST API_ configuration

The configuration file `api.ini` provides several options important for proper working
the _n6 REST API_, especially concerning application, server and logging  configuration. All options are described in detail in the `api.ini` file comments.


## _n6 Portal_

First, install `npm` and `yarn`:

```bash
$ sudo apt-get install -y nodejs npm
$ sudo npm i npm@latest -g
$ sudo npm install --global yarn
```

Update `node`. Recommended version is current LTS. One of the easiest ways to update
`node` is through the _n_ Node.js Version Manager:

```bash
$ sudo npm install -g n
$ sudo n lts
```

If the command:

```bash
$ node --version
```

still returns the old version, open a new shell.

### Deployment

Install dependencies and build GUI application:

```bash
# Important: commands should be launched in virtualenv
(env_py3k)$ cd /home/dataman/n6/N6Portal/react_app
(env_py3k)$ yarn
(env_py3k)$ yarn build
```

!!!note

    Before building the GUI application or running a development server, it may be required
    to configure the application first. The mini web application should be used as a graphical
    user interface for configuration. See the
    [_n6 Portal_ GUI Configuration section](#n6-portal-gui-configuration) for further details.

Set up connections to the databases in configuration file `/home/dataman/n6/etc/web/conf/portal.ini`:

```ini
sqlalchemy.url = mysql://root:password@localhost/n6
auth_db.url = mysql://root:password@localhost/auth_db
```

!!!note

    The URL of the database depends on the location of the database and installed
    N6Portal API application. If they are kept on the same host, then `localhost`
    can be used as an address of the database. Otherwise, it should be replaced
    with an address of the host serving the database. In the latter case the SQL
    database server should be configured to allow remote connections:
    [configuration instructions](#access-to-remote-sql-database)


Also replace default server secrets in options related to mfa, web tokens and api key.
You can generate a safe secret string using this command:
```bash
$ python3 -c 'import os, base64; print(base64.b64encode(os.urandom(40), b"-_").decode())'
```

```ini
web_tokens.token_type_to_settings =
    {
        'for_login': {
            'server_secret': <secret string>,
            'token_max_age': 60,
        },
        'for_mfa_config': {
            'server_secret': <secret string>,
            'token_max_age': 3600,
        },
        'for_password_reset': {
            'server_secret': <secret string>,
            'token_max_age': 3600,
        },
    }
web_tokens.server_secret_for_pseudo_tokens = <secret string>
mfa.server_secret = <secret string>
api_key_based_auth.server_secret = <secret string>
```

Copy (as `root`) the Apache2 config from `n6/etc/apache2/sites-available/n6-portal.conf`
to `/etc/apache2/sites-available/` and edit the file:

```bash
$ sudo cp /home/dataman/n6/etc/apache2/sites-available/n6-portal.conf /etc/apache2/sites-available/
$ sudo a2ensite n6-portal
$ systemctl restart apache2
```

The _n6 Portal_ should be accessible via `https://server_IP_or_FQDN/`
(where `server_IP_or_FQDN` is the address of your Apache server).
_n6 Portal_ has implemented two-factor authentication, which needs security token as a second
factor to authenticate logging user. For creating securty token you can use an open-source 2FA
tool (for example free-OTP or Google authenticator).

### _n6 Portal_ Configuration

#### Back-end Application

The configuration file `portal.ini` provides necessary options important for _n6 Portal_ component,
especially configurations related to authentication policy, mfa and web tokens, api key, databases
`event_db` and `auth_db`, mail notices, rt_client, logging and more. All options are described
in detail in the `portal.ini` file comments.

#### _n6 Portal_ GUI Configuration

A mini web application, ran inside GUI's `yarn` environment, may be used to easily configure
the _n6 Portal_ GUI application. Configurable options are: _n6 Portal_ API URL
(URL of the _n6 Portal_ back-end application; it should be specifically set
if GUI and API are hosted in diferrent origins, e.g., different host, different port)
and a location of locale files - JSON files that contain sets of text strings and translations
used in GUI's web pages.

Locale files may be edited through the configuration application. Currently, it is possible
to edit texts and labels related to the _Terms of Service_ page (it is shown before a sign-up
form). Default locale files contain _Terms of Service_ template. Texts should be edited
in order to customize the terms of using the application.

The configuration app is available after `yarn` dependencies have been installed. Go to
a directory containing the GUI application (`/home/dataman/n6/N6Portal/react_app` by default)
and use a command below to run a development server, which will serve the app:

```bash
$ yarn run config
```

The web application will be served at `http://0.0.0.0:3001` by default. Go to the address
(it should be available from the localhost as well as from remote host) from a web browser.

On the first screen two options can be set:

* `n6Portal API URL` - it may be a relative address, e.g., an alias to the API (`/api`
by default) or an absolute address, like `https://192.168.56.1/api`. An absolute address
should be set if GUI and API are hosted in different origins. See
the [_Hosting GUI and API in different origins_ section](#hosting-gui-and-api-in-different-origins)
for further details.
* `Path to Terms of Service Locale JSON File` - an absolute path to a directory containing
the locale files. If the input is left empty, a default path will be used (`config/locale`
directory inside the GUI directory). Otherwise, an empty or nonexistent directory may be used,
so the templates of locale files will be saved there. Or it can be a path to directory that
already contains locale files. In the latter case the directory must contain a proper
subdirectories structure and JSON files must have all the required fields. If you do not have
a directory containing locale files, choose an empty directory first, so templates can be
saved, and then they may be customized.

To save the settings, click the `Save current settings` button. Then, click `Go to next view`.
This view presents two forms representing English and Polish locale files. The _List of Terms_
section contains a list of terms. Terms may be deleted and added. Other inputs represent
single text, header or message, being a part of the _Terms of Service_.

The _Version of document_ input is an exception. It is a read-only field that is modified
after saving changes to locale file. Its value is a string that identifies a version
of file's content. It contains date and time when the file has been saved, language tag,
and a hash of file's content.

After customizing the locale, click the `Save current locale` button. If it succeeds, then
changes have been saved in configuration and locale files. The web application can be closed
and the development server may be terminated (CTRL+C).

For the changes to be applied, GUI has to be build again, or if it is served via a development
server, it should be restarted.

#### Access to Remote SQL Database

##### Address to Bind

Locate the `bind-address` option in MariaDB configuration files, in the `mysqld` section. It is
usually in `/etc/mysql/my.cnf` or in `/etc/mysql/mariadb.conf.d/50-server.cnf` in case
of serving the database via Docker. It can be easily located using `rgrep`:

```bash
$ rgrep bind-address /etc/mysql
```

MariaDB is usually bound to the loopback interface (127.0.0.1) by default. Edit the configuration
file to set the `bind-address` to the address of a remote host, which will connect to
the database, or to `0.0.0.0` in order to accept connection from every IP address.

##### Granting User Connections from Remote Host

Log into the MariaDB command line client:

```bash
$ mysql -u root -ppassword
```

Create a new user and grant him privileges:

```mysql
CREATE USER '<username>'@'<address>' IDENTIFIED BY '<password>';
GRANT ALL PRIVILEGES ON *.* TO '<username>'@'<address>';
```

Replace the placeholders with actual values:

* `<username>` - name of the newly created user
* `<address>` - address of the remote host
* `<password>` - user's password

For more detailed instructions, see
[the MariaDB documentation](https://mariadb.com/kb/en/configuring-mariadb-for-remote-client-access/).

#### Hosting GUI and API in Different Origins

If GUI and _n6 Portal_ API applications are being served on different hosts, their protocols
are different (e.g., GUI is accessed through http:// URL and API - through https://) or ports,
the **CORS** (Cross-Origin Resource Sharing) mechanism should be configured to allow GUI
to connect to API. [Article on CORS.](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

Let us consider the example, where GUI application is being served on one host, and
is accessible through `http://192.168.56.101:8080`. The backend _n6 Portal_ API application
is configured on the other host, being accessible through `https://192.168.56.102/api`.

When the GUI is being accessed in browser, and it makes request to API
on `https://192.168.56.102/api`, the request will be blocked with an error like _Cross-Origin
Request Blocked..._

First, the API URL has to be set in GUI's configuration.
[Open the configuration web app](#n6-portal-gui-configuration), set the `n6Portal API URL` field
to `https://192.168.56.102/api`.

Then, CORS headers should be added to Apache2 application's configuration. Make sure that
the _headers_ module is enabled:

```bash
$ sudo a2enmod headers
```

In the configuration file of the `n6 Portal` application:
`/etc/apache2/sites-enabled/n6-portal.conf`, inside the `<VirtualHost>` section or one of
following section: `<Directory>`, `<Location>`, `<Files>`, add:

```ini
Header set Access-Control-Allow-Origin "http://192.168.56.101:8080"
Header set Access-Control-Allow-Credentials true
```

The `*` (asterisk) sign may be used instead of `http://192.168.56.101:8080`, which allows
cross-origin requests from all websites. However, it is not recommended.

If the address `http://192.168.56.101:8080` is set to allow cross-origin requests from, then
this address should be used to access GUI. Even if, for example, `192.168.56.101` is
a `localhost`, GUI should not be accessed through `http://localhost:8080` URL.

More articles on setting the CORS headers:
* <https://enable-cors.org/server_apache.html>
* <https://ubiq.co/tech-blog/enable-cors-apache-web-server/>

### Troubleshooting

There are a few possible causes:

> #### n6 Portal Api is not working
>
> Check if _n6 Portal API_ is available using CURL. In case of wrong configuration,
> the API should throw an error with 500 status code.

    $ cd ~/certs
    $ curl --cert cert.pem --key key.pem -k 'https://localhost/api/info'

> Proper result:

    $ {"authenticated": false}

> If you get the `500 Internal Server Error` message, then there is something
> wrong with:
>
> - `n6-portal.conf` Apache2 configuration. Check whether all paths there are valid.
> - `n6/etc/web/wsgi/portal.wsgi`: check if the path in `ini_path` is valid
> - `n6/etc/web/conf/portal.ini` : check options: `sqlalchemy.url` and
>   `auth_db.url`

> #### Other issues
>
> Check the _n6_ Apache logs (`/var/log/apache2/*-n6*.log`) to look into the cause of an issue.
> Consider creating an issue at _n6_ GitHub project:
> [https://github.com/CERT-Polska/n6](https://github.com/CERT-Polska/n6)

## _n6 Admin Panel_

Copy the example _n6 Admin Panel_ configuration files to the directory with _n6_ config files:

```bash
(env_py3k)$ cp /home/dataman/n6/N6AdminPanel/n6adminpanel/admin_panel.conf /home/dataman/.n6
```

It is recommended to generate a random string to be used as the secret key for your instance
of the _n6 Admin Panel_ application:

```bash
(env_py3k)$ python -c 'import os, base64; print(base64.b64encode(os.urandom(32), b"-_").decode())'
```

Set the resultant random string as the value of the `app_secret_key` option in the `[admin_panel]`
section of the `/home/dataman/.n6/admin_panel.conf` configuration file.

```ini
[admin_panel]
app_secret_key = <generated_string>
```

Copy (as root) the Apache2 configuration file for _n6 Admin Panel_ from
`/home/dataman/n6/etc/apache2/n6-adminpanel.conf`
to `/etc/apache2/sites-available/n6-adminpanel.conf`:

```bash
$ cp /home/dataman/n6/etc/apache2/sites-available/n6-adminpanel.conf /etc/apache2/sites-available/
```

Then enable the site and reload Apache2 configuration (as root):

```bash
$ sudo a2ensite n6-adminpanel
$ systemctl reload apache2
```

The _n6_ Admin Panel should be accessible via `https://server_IP_or_FQDN:4444/` (where
`server_IP_or_FQDN` is the address of your Apache server).

!!! warning

    The example *n6 Admin Panel* website configuration has no authentication!
    (So, in particular, do not make that website public!)

# HTTP Services

> **Note**: to complete any of the steps described below you need to have:
>
> * installed the relevant *n6* component(s); see: section [Installation of n6 components](n6_core.md)
> * the *Auth DB* created; see: section [n6 Configuration for SQL databases](configuration.md#n6-configuration-for-mysqldb)
> * generated certificates; see: section [Certificates](certs.md)


## *n6 Admin Panel*

Copy the example *n6 Admin Panel* configuration files to the directory with *n6* config files:

```bash
(env)$ cp /home/dataman/n6/N6AdminPanel/n6adminpanel/admin_panel.conf /home/dataman/.n6
```

Run the following command to generate a random string, that will be used as a secret key
for the *n6 Admin Panel* application:

```bash
(env)$ python -c 'import os, base64; print(base64.b64encode(os.urandom(16), b"-_").decode())'
```

Set the resultant random string as the value of the `app_secret_key` option in the `[admin_panel]`
section of the `/home/dataman/.n6/admin_panel.conf` configuration file:

```ini
[admin_panel]
app_secret_key = <generated_string>
```

Copy (as root) the Apache2 configuration file for *n6 Admin Panel* from
`/home/dataman/n6/etc/apache2/n6-adminpanel.conf`
to `/etc/apache2/sites-available/n6-adminpanel.conf`:

```bash
$ cp /home/dataman/n6/etc/apache2/sites-available/n6-adminpanel.conf /etc/apache2/sites-available/
```

Then enable the site and reload Apache2 configuration (as root):

```bash
$ a2ensite n6-adminpanel
$ systemctl reload apache2
```

The *n6* Admin Panel should be accessible via `https://server_IP_or_FQDN:4444/` (where
`server_IP_or_FQDN` is the address of your Apache server).

**WARNING:** the example *n6 Admin Panel* website configuration has no authentication!
(So, in particular, do not make this website public!).


## *n6 REST API*

Set up database connection addresses in `/home/dataman/n6/etc/web/conf/api.ini` (*Pyramid*
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
$ echo 'ServerName localhost' >> /etc/apache2/apache2.conf
```

Enable the website:

```bash
$ a2ensite n6-api
$ systemctl restart apache2
```

### Querying the API

```bash
(env)$ cd ~/certs
(env)$ curl --cert cert.pem --key key.pem -k 'https://localhost:4443/search/events.json?time.min=2015-01-01T00:00:00'
[

]
```

This response means the *event* database is empty. 


## *n6 Portal*

First, install `npm`:

```bash
$ apt-get install -y nodejs npm
$ npm i npm@latest -g
```

Copy and replace `config.json` in `N6Portal/gui/src/config/`:

```bash
(env)$ cp -f /home/dataman/n6/etc/web/conf/gui-config.json /home/dataman/n6/N6Portal/gui/src/config/config.json
```

### GUI customization [at least some parts are to be deprecated]

#### Customize the text of registration terms

When user switches to *Sign-up* view in *n6 Portal*, he has to accept the Terms and Conditions
of using the system. By default, it is the text of terms by NASK and CERT Polska. When
establishing your own instance of *n6 Portal*, you probably may want to change it to your
own terms and conditions. You can do it before deploying the Vue.js application, by modifying
contents of `/home/dataman/n6/N6Portal/gui/src/locales/<LANGUAGE_TAG>/register_terms.json`,
where `<LANGUAGE_TAG>` is a symbol of language the texts are in. JSON object's keys stand for:

* `pageTitle` - title of the view the user is redirected to (a sign-up form).
* `title` - title of the text.
* `precaution` - a short introduction, describing the initial requirements.
* `terms` - list of terms of usage; list elements will be displayed as ordered list. You can
  delete or add another points of terms, the list is generated in HTML.
* `checkboxLabel` - value of the `label` HTML element, describing the checkbox, which has to
  be checked in order to accept the terms.
* `okLabel` - label in `OK` button.
* `cancelLabel` - label in `Cancel` button.
* `errorFlashMsg` - text of an error message, displayed when user tries to proceed without
  accepting the terms.

Currently, texts, messages, labels etc. in *Sign-up* GUI components are in English (`EN`)
and Polish (`PL`).
A feature to allow to choose custom languages, or keep one language only, is to be released soon.
Right now, if you do not need Polish localization, you can for example edit out the
language-switching buttons.

### Deployment [at least some parts are to be deprecated]

Install dependencies and build GUI application:

```bash
# Important: commands should be launched in virtualenv
(env)$ cd /home/dataman/n6/N6Portal/gui
(env)$ npm install
(env)$ npm run build
```

Set up connections to the databases in `/home/dataman/n6/etc/web/conf/portal.ini`:

```ini
sqlalchemy.url = mysql://root:password@localhost/n6
auth_db.url = mysql://root:password@localhost/auth_db
```

Copy (as root) the Apache2 config from `n6/etc/apache2/sites-available/n6-portal.conf`
to `/etc/apache2/sites-available/` and edit the file:

```bash
$ cp /home/dataman/n6/etc/apache2/sites-available/n6-portal.conf /etc/apache2/sites-available/
$ a2ensite n6-portal
$ systemctl restart apache2
```

The *n6* Portal should be accessible via `https://server_IP_or_FQDN/`
(where `server_IP_or_FQDN` is the address of your Apache server).

### Troubleshooting [at least some parts are to be deprecated]

**[ERROR]: Certificate not found. Add it in the browser to log in**

There are a few possible causes:

> #### n6 Portal Api is not working
>
> Check if *n6 Portal API* is available using CURL. In case of wrong configuration,
> the API should throw an error with 500 status code.
>
    (env)$ cd ~/certs
    (env)$ curl --cert cert.pem --key key.pem -k 'https://localhost/api/info'
> Proper result:
>
    (env)$ {"certificate_fetched": true, "authenticated": false}

> If you get the `500 Internal Server Error` message, then there is something
> wrong with:
>
> * `n6-portal.conf` Apache2 configuration. Check whether all paths there are valid.
> * `n6/etc/web/wsgi/portal.wsgi`: check if the path in `ini_path` is valid
> * `n6/etc/web/conf/portal.ini` : check options: `sqlalchemy.url` and
> `auth_db.url`

> #### Certificate is not imported into browser

> To browse the *n6 Portal GUI*, a web browser needs a certificate. Convert the certificate
> in `~/certs` into the `p12` file format and import it into the browser. Use `openssl`
> to do the conversion:
>   
    (env)$ cd ~/certs
    (env)$ openssl pkcs12 -export -out ImportMetoWebBrowser.p12 -in cert.pem -inkey key.pem
    (env)$ chmod 777 ImportMetoWebBrowser.p12
    ```
> Now import the generated `.p12` certificate into your web browser. This feature is usually
> available in advanced/private settings of a browser.

> **Wrong credentials**

>    Generated certificates are used for user authentication/authorization and to provide
>    secure connection.
>
>    Make sure that your organization and your user exist in *Auth DB* through
>    the *n6 Admin Panel* (`https://localhost:4444`).
>
>    Parts of a generated certificate's subject, that take part in authentication process,
>    can be set as variables' values of a source code of the `~/certs/generate_certs.sh` script:
>
    (env)$ cat ~/certs/generate_certs.sh
    ...
    CN=login@example.com
    ORG=example.com
    ```

>    A value `ORG=example.com` means that you should find a record with an `org_id` field set to
>    `example.com` at `https://localhost:4444/org/`.
>    
>    A value `CN=login@example.com` means that you should find a record with a `login` field
>    set to `login@example.com` at `https://localhost:4444/org/`. Examine the row and ensure
>    that the user is related to the `Org "example.com"` organization record.


> #### Other issues
>
> Check the *n6* Apache logs (`/var/log/apache2/*-n6*.log`) to look into the cause of an issue.
> Consider creating an issue at *n6* GitHub project:
>[https://github.com/CERT-Polska/n6](https://github.com/CERT-Polska/n6)

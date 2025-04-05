# Configuration of *n6 Stream API*

The *n6 Stream API* installation is based on Debian 12.
This guide describes how to install [*n6 Stream Api*](../../usage/streamapi.md) along with a **second** RabbitMQ on **another** server, **different** than main *n6* instance.

The simplified data flow of the `n6 Stream Api`:

```
                      n6's internal pipeline
                              |
                          event data
                              ↓
                        n6anonymizer
                              |
                  event data per client organization
                              ↓
                    Stream API Server (RabbitMQ)

------------------------------------------------------------------------------

                            Client
                              |
                      initial STOMP communication
                              ↓
                    Stream API Server ←→ Broker Auth API + Auth DB 
                              |        (authenticaion & authorization)
                              |
                    event data per client organization
                              ↓
                            Client
```

## System preparation

Follow the official guide to add the system repository for Erlang and RabbitMQ, preferably with RabbitMQ 3.12 
https://www.rabbitmq.com/docs/install-debian

Install packages:

```
$ apt update
$ apt install rabbitmq-server apache2 pip libapache2-mod-wsgi-py3 python3-virtualenv
$ git clone https://github.com/CERT-Polska/n6.git
```

!!! Note
    Remember to also install the essential Debian packages.

### RabbitMQ configuration

#### Enable plugins:
Enable these plugins by running the `rabbitmq-plugins` command

```
[E*] rabbitmq_auth_backend_http        3.12.6
[E*] rabbitmq_auth_mechanism_ssl       3.12.6
[E*] rabbitmq_federation               3.12.6
[E*] rabbitmq_federation_management    3.12.6
[E*] rabbitmq_management               3.12.6
[e*] rabbitmq_management_agent         3.12.6
[E*] rabbitmq_shovel                   3.12.6
[E*] rabbitmq_shovel_management        3.12.6
[E*] rabbitmq_stomp                    3.12.6
[e*] rabbitmq_web_dispatch             3.12.6
```

### Create RabbitMQ config:

!!! Note
    Configuration below assumes you have your own `/etc/rabbitmq/rabbitmq.conf` file.
    You can copy and adjust it from `/n6/etc/rabbitmq/conf/rabbitmq.conf` or create one by yourself.

Based on the below template, create `/etc/rabbitmq/advanced.config`.

```
[
  {rabbit, [
     {auth_backends, [rabbit_auth_backend_internal, rabbit_auth_backend_http]},
     {auth_mechanisms, ['EXTERNAL']},
     {loopback_users, []}]},

{rabbitmq_stomp, [
  {auth_backends, [rabbit_auth_backend_http]},
  {log, true},
  {implicit_connect, false},
  {ssl_cert_login, false},
  {ssl_listeners, [61614]},
  {tcp_listeners, []}
  ]
},

{rabbitmq_auth_backend_http,
   [{http_method,   post},
    {user_path,     "http://localhost/user"},
    {vhost_path,    "http://localhost/vhost"},
    {resource_path, "http://localhost/resource"},
    {topic_path,    "http://localhost/topic"}
  ]
}
].

```
!!! warining "Disclaimer: Do not forget about the x509 server certificates"
    Generate the x509 server certificates and place them in appropriate folder,

### Fine-tunning the  <u>Main Broker</u> Configuration via GUI:
Create User and Password  for the Federation connection.

* Go to `Admin → Users → Add user`
* Create `Username` and `Password` then `Add user`.
* Add all permissions to the Virtual Host `/`

### Fine-tunning the <u>Stream API broker</u>  RabbitMQ configuration via GUI


* In the browser navigate to https://localhost:15672

* Create federation to federate all events from main broker from Exchange `event` to local exchange:
    * Go to `Admin → Federation Upstreams`
    * Click on `Add a new upstream`
    * Fill in the form with the config given below to the corresponding fields.

```config
URI: amqp://user:password@main-broker-fqdn.com:5672
Prefetch Count: 20
Ack Mode: on-confirm
Expires: 36000000ms
```

* Create a policy to match all events from the federation:
    *  Go to `Admin → Policies → Add policy`.
    *  Fill in the form with the config given below to the corresponding fields.

```config
Name: p-event
Pattern: ^event$
Apply to: Exchanges and queues
Priority: 0
Definition: federation-upstream-set: all
```

### n6 preparation

* Install the n6 Data Pipeline inside a new virtualenv environment:

```bash
$ virtualenv venv-n6datapipeline
$ source venv-n6datapipeline/bin/activate
(venv-n6datapipeline) $ cd n6
(venv-n6datapipeline) $ python do_setup.py N6DataPipeline
```

!!! Note
      If during the `python do_setup.py N6DataPipeline` command you encountered any errors, try:

      ```
      (venv-n6datapipeline) $ pip install setuptools==68.1.0
      ```

#### Create n6 configuration

* Place the content of `00_global.conf` and `00_pipeline.conf` in a new directory:

```bash
$ mkdir ~/.n6
```

`$ cat ~/.n6/00_global.conf`

```
[rabbitmq]
host = n6stream.fqdn.com
port = 5671
ssl = true
ssl_ca_certs = /opt/n6user/cacert.pem
ssl_certfile = /opt/n6user/n6stream.pem
ssl_keyfile = /opt/n6user/n6stream.key
heartbeat_interval = 30
```


`$ cat ~/.n6/00_pipeline.conf `

```
[pipeline]
aggregator = parsed
enricher = parsed, aggregated
comparator = enriched
filter = enriched, compared
anonymizer = filtered
recorder = filtered
counter = recorded
```

* Place the following content, the n6 Auth DB database config into  `~/.n6/09_auth_db.conf`

```
[auth_db]
url = mysql://user-in-mariadb@n6db.fqdn.com/auth_db
ssl_cacert = /opt/n6user/ssl/cacert.pem
ssl_cert = /opt/n6user/ssl/n6stream-client.pem
ssl_key = /opt/n6user/ssl/n6stream-client.key

[auth_db_session_variables]
wait_timeout = 7200

[auth_db_connection_pool]
pool_pre_ping = true
pool_recycle = 3600
pool_timeout = 20
pool_size = 15
max_overflow = 12
```

* Add simple syslog-logging config into `~/.n6/logging.conf`:

```
# See: https://docs.python.org/library/logging.config.html#configuration-file-format

#
# Declarations

[loggers]
keys = root

[handlers]
keys = syslog, console

[formatters]
keys = standard, cut_notraceback

# Loggers

[logger_root]
level = INFO
handlers = syslog

# Handlers

[handler_console]
class = StreamHandler
level = INFO
formatter = standard
args = (sys.stderr,)

[handler_syslog]
class = handlers.SysLogHandler
level = ERROR
formatter = cut_notraceback
args = ('/dev/log',)

# full information
[formatter_standard]
format = n6: %(levelname) -10s %(asctime)s %(name) -25s in %(funcName)s() (#%(lineno)d): %(message)s

# brief information: no tracebacks, messages no longer than ~2k
[formatter_cut_notraceback]
format = n6: %(levelname) -10s %(asctime)s %(name) -25s in %(funcName)s() (#%(lineno)d): %(message)s
class = n6lib.log_helpers.NoTracebackCutFormatter
```

* Finally, run n6anonymizer to create the required exchanges:

```bash
(venv-n6datapipeline) $ n6anonymizer
```



* Install the n6 Broker Auth API inside a new virtualenv environment:

```bash
$ virtualenv venv-n6brokerauthapi
$ source venv-n6brokerauthapi/bin/activate
(venv-n6brokerauthapi) $ cd n6
(venv-n6brokerauthapi) $ python do_setup.py N6BrokerAuthApi
```

!!! Note
      If during the `python do_setup.py N6BrokerAuthApi` command you encountered any errors, try:

      ```
      (venv-n6brokerauthapi) $ pip install setuptools==68.1.0
      ```

* Create configuration for the n6 Broker Auth Api

```bash
$ mkdir ~/apa_config
$ cp n6/etc/web/conf/brokerauthapi.ini apa_config/
```

* Change the appropriate lines in `~/apa_config/brokerauthapi.ini`. Pay attention to the required `auth_db.url`:

```
(...)
auth_db.url = mysql://user-in-mariadb@n6db.fqdn.com/auth_db
auth_db.ssl_cacert = /opt/n6user/ssl/cacert.pem
auth_db.ssl_cert = /opt/n6user/ssl/n6stream-client.pem
auth_db.ssl_key = /opt/n6user/ssl/n6stream-client.key
(...)
stream_api_broker_auth.server_secret = INSECURE EXAMPLE VALUE THAT MUST BE REPLACED
(...)
```

* Create a WSGI launcher for the Apache2 server:

`$ cat ~/apa_config/brokerauthapi.wsgi` 

```
#!/usr/bin/env python
import n6lib  # noqa
from pyramid.paster import get_app, setup_logging
ini_path = '/opt/n6user/apa_config/brokerauthapi.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')
```

* Create the python-eggs cache directory for the app:

```bash
$ mkdir ~/apa_config/python-eggs
$ chmod -R 777 ~/apa_config/python-eggs
```

### Apache2 web server configuration

* Enable wsgi module

```
$ a2enmod wsgi
```

* Create the Apache2 configuration for the n6 app:

`$ cat /etc/apache2/sites-available/n6-brokerauthapi.conf`

```
<VirtualHost 127.0.0.1:80>
    ServerName n6-brokerauthapi.fqdn.com
    ServerAlias n6-brokerauthapi	
        
	WSGIApplicationGroup %{GLOBAL}
        WSGIDaemonProcess n6-brokerauthapi python-path=/opt/n6user/venv-n6brokerauthapi/lib/python3.11/site-packages python-eggs=/opt/n6user/apa_config/python-eggs
        WSGIScriptAlias / /opt/n6user/apa_config/brokerauthapi.wsgi process-group=n6-brokerauthapi application-group=%{GLOBAL}

        <Directory /opt/n6user/apa_config>
          Require all granted
          WSGIProcessGroup n6-brokerauthapi
         <IfModule mod_rewrite.c>

           RewriteEngine On
           RewriteBase /
                    
           RewriteRule ^index\.html$ - [L]
           RewriteCond %{REQUEST_FILENAME} !-f
           RewriteCond %{REQUEST_FILENAME} !-d
           RewriteRule . /index.html 
          
         </IfModule>
        </Directory>

        ServerAdmin webmaster@localhost
        
        ErrorLog ${APACHE_LOG_DIR}/n6-brokerauthapi.error.log
        LogLevel error
        LogFormat "%{%Y-%m-%dT%H:%M:%S%z}t %{Authorization}i \"%r\" %>s %B %D \"" n6_log
        CustomLog ${APACHE_LOG_DIR}/n6-brokerauthapi.access.log n6_log
 
</VirtualHost>
```

!!! Note
    Remember that python-path contains python version(which might be different for you).

* Enable the Apache2 configuration and reload

```
$ a2ensite n6-brokerauthapi
$ systemctl reload apache2
```

### Configuration stream API access 

In n6adminpanel, create a new Organization and a user within. Make sure the `Stream Api Enabled` option is checked.

* Sync the org config with the stream api brok config:

Inside the virtual enviroment, run `exchange_updater`:

```
(venv-n6datapipeline)$ python ~/n6/N6DataPipeline/n6datapipeline/aux/exchange_updater.py
```

### Testing

* Make sure the `n6annonymizer` is running within the `venv-n6datapipeline` env. Supervisor mode is preferred.
* Connect to the STOMP server based on the stream api [wiki](../../usage/streamapi.md)
* Push some data into the n6 pipeline. Make sure the organization that the user is connected to has all the necessary rights to read those events. The access list is the same as in the REST API and Portal
* Events should be received by the connected client

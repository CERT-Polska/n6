<style>
  code.language-bash::before{
    content: "$ ";
  }
</style>


# *n6 Portal* -- Some Finer Points

## GUI Customization

A mini web application, ran inside GUI's `yarn` environment, may be used to easily customize
the _n6 Portal_ GUI application. Configurable options are: _n6 Portal_ API URL
(URL of the _n6 Portal_ back-end application; it should be specifically set
if GUI and API are hosted in different origins, e.g., different host, different port)
and a location of locale files -- JSON files that contain sets of text strings and translations
used in GUI's web pages.

Locale files may be edited through the configuration application. Currently, it is possible
to edit texts and labels related to the _Terms of Service_ page (it is shown before a sign-up
form). Default locale files contain _Terms of Service_ template. Texts should be edited
in order to customize the terms of using the application.

The configuration app is available after `yarn` dependencies have been installed. Go to
a directory containing the GUI application (`/home/dataman/n6/N6Portal/react_app` by default)
and use a command below to run a development server, which will serve the app:

```bash
yarn run config
```

The web application will be served at `http://0.0.0.0:3001` by default. Visit the address
(it should be available from the localhost as well as from remote host) using a web browser.

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

## Hosting GUI and API in Different Origins

If GUI and _n6 Portal_ API applications are being served on different hosts, their protocols
are different (e.g., GUI is accessed through http:// URL and API - through https://) or ports,
the **CORS** (Cross-Origin Resource Sharing) mechanism should be configured to allow GUI
to connect to API.

!!! note ""

    **See also:** [https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)

Let us consider the example, where GUI application is being served on one host, and
is accessible through `http://192.168.56.101:8080`. The backend _n6 Portal_ API application
is configured on the other host, being accessible through `https://192.168.56.102/api`.

When the GUI is being accessed in browser, and it makes request to API
on `https://192.168.56.102/api`, the request will be blocked with an error like _Cross-Origin
Request Blocked..._

First, the API URL has to be set in GUI's configuration.
Open the [configuration web app](#gui-customization), set the `n6Portal API URL` field
to `https://192.168.56.102/api`.

Then, CORS headers should be added to Apache2 application's configuration. Make sure that
the _headers_ module is enabled:

```bash
sudo a2enmod headers
```

In the configuration file of the `n6 Portal` application:
`/etc/apache2/sites-enabled/n6-portal.conf`, inside the `<VirtualHost>` section or one of
following section: `<Directory>`, `<Location>`, `<Files>`, add:

```ini
Header set Access-Control-Allow-Origin "http://192.168.56.101:8080"
Header set Access-Control-Allow-Credentials true
```

The `*` (asterisk) character may be used instead of `http://192.168.56.101:8080`, which allows
cross-origin requests from all websites. However, it is not recommended for security reasons.

If the address `http://192.168.56.101:8080` is set to allow cross-origin requests from, then
this address should be used to access GUI. Even if, for example, `192.168.56.101` is
a `localhost`, GUI should not be accessed through `http://localhost:8080` URL.

!!! note ""

    **See also:**

    * <https://enable-cors.org/server_apache.html>
    * <https://ubiq.co/tech-blog/set-access-control-allow-origin-cors-headers-apache/>
    * <https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/11-Client-side_Testing/07-Testing_Cross_Origin_Resource_Sharing>

# Certificates

It is recommended to encrypt communication between *n6* and other *n6* components/tools,
and to provide passwordless authentication. Use your own x509 certificates in production environment, 
or create some CA certificate and use it to sign some test certificates in development
environment. You can use the provided bash script, `generate_certs.sh`, to generate
the CA and one *server/client* certificate:

```bash
$ mkdir ~/certs
$ cp /home/dataman/n6/etc/ssl/generate_certs.sh ~/certs
$ cp /home/dataman/n6/etc/ssl/openssl.cnf ~/certs
$ cd /home/dataman/certs
```

Just before running the script, modify the `generate_certs.sh` file to set generated certificate's
subject parts, e.g.:

```text
CN=login@example.com
ORG=example.com
```

**Important: values `CN` and `ORG` have to match user's logging and organization ID he belongs to,
so they must be the same as login and organization ID added by the `n6populate_auth_db` command!**

```bash
$ ./generate_certs.sh
+ DAYS=1365
+ CN=login@example.com
+ ORG=example.com
...
Signature ok
The Subject's Distinguished Name is as follows
commonName            :ASN.1 12:'login@example.com'
organizationName      :ASN.1 12:'example.com'
Certificate is to be certified until May 18 10:35:10 2023 GMT (1365 days)

Write out database with 1 new entries
Data Base Updated
```

Script should generate some files. Most important are:
* _cert.pem_
* _key.pem_
* _N6-CA/cacert.pem_

Generated files will be used to authenticate some requests to _n6 Rest API_. Authentication
to _n6 Portal_ (GUI) will be executed by the certificate converted to _p12_ format, imported to
a browser:

```bash
$ openssl pkcs12 -export -out ImportMetoWebBrowser.p12 -in cert.pem -inkey key.pem
```

Using your favourite browser, import the converted certificate _p12_ file
`ImportMetoWebBrowser.p12` using browser's advanced settings.

# Certificates

!!! note

    The following examples assume the home directory path is `/home/dataman`
    and the project directory path is `/home/dataman/n6`.

!!! note

    Self-signed certificates are inherently insecure (since they lack a chain of trust). 
    Please contact your IT Admin if you are unsure/unaware of the consequences of generating & 
    using self-signed certificates. These instructions should be used for development environments only.

It is recommended to encrypt communication between _n6_ and other _n6_ components/tools,
and to provide passwordless authentication. Use your own x509 certificates in production environment,
or create some CA certificate and use it to sign some test certificates in development
environment. You can use the provided bash script, `generate_ca.sh`, to generate
the CA and `generate_certs.sh` _server/client_ certificate:

```bash
$ mkdir ~/certs
$ cp /home/dataman/n6/etc/ssl/generate_ca.sh ~/certs
$ cp /home/dataman/n6/etc/ssl/generate_certs.sh ~/certs
$ cp /home/dataman/n6/etc/ssl/openssl.cnf ~/certs
$ cd /home/dataman/certs
```

Just before running the script, modify the `generate_certs.sh` file to set generated certificate's
subject parts, e.g.:

```bash
CN=login@example.com
ORG=example.com
```

**Important: values `CN` and `ORG` have to match user's logging and organization ID he belongs to,
so they must be the same as login and organization ID added by the `n6populate_auth_db` command!**

Generate the self-signed root CA certificate, by running the command only once:

```bash
$ ./generate_ca.sh
+ DAYS=1365
+ OPENSSL_CNF=openssl.cnf
+ mkdir -p n6-CA/certs n6-CA/private
+ touch n6-CA/index.txt
+ touch n6-CA/index.txt.attr
+ echo 12
+ openssl req -x509 -config openssl.cnf -newkey rsa:2048 -days 1365 -out generated_certs/n6-CA/cacert.pem -outform PEM -subj /CN=n6-CA/ -nodes
Generating a RSA private key
.................+++++
....................................+++++
writing new private key to 'n6-CA/private/cakey.pem'
```

Generate the server/client certificate, by running the command, as many times as you want.
Do not forget increment the serial number if the certificate with the same serial.

```bash
$ ./generate_certs.sh
+ DAYS=1365
+ CN=login@example.com
+ ORG=example.com
+ OPENSSL_CNF=openssl.cnf
+ echo 12
+ openssl genrsa -out generated_certs/key.pem 2048
Generating RSA private key, 2048 bit long modulus (2 primes)
........................+++++
............+++++
e is 65537 (0x010001)
+ openssl req -new -key key.pem -out generated_certs/req.csr -outform PEM -subj /CN=login@example.com/O=example.com/ -nodes
+ openssl ca -config openssl.cnf -in generated_certs/req.csr -out generated_certs/cert.pem -days 1365 -notext -batch -extensions server_and_client_ca_extensions
Using configuration from openssl.cnf
Check that the request matches the signature
Signature ok
The Subject's Distinguished Name is as follows
commonName            :ASN.1 12:'login@example.com'
organizationName      :ASN.1 12:'example.com'
Certificate is to be certified until Oct 27 15:46:19 2025 GMT (1365 days)
Write out database with 1 new entries
Data Base Updated
```

Script should generate some files. Most important are:

- _cert.pem_
- _key.pem_
- _N6-CA/cacert.pem_

Generated files will be used to authenticate some requests to _RabbitMQ_.
# n6manage

The purpose of the `n6manage` script is to manage your _n6_'s public key
infrastructure, in particular, to create your certificates, as well as
to store and retrieve them in/from the _n6_'s Auth DB.

!!! warning

    This document is still a draft.

## Generating certificates for the use of `n6manage` component

You can find certificate examples below, but bear in mind that these are only examples - they **should never be used for production!**

```
N6Lib/n6lib/tests/certs_and_requests_for_testing/test_for_n6_manage_admin.csr
N6Lib/n6lib/tests/certs_and_requests_for_testing/test_for_n6_manage_client.csr
N6Lib/n6lib/tests/certs_and_requests_for_testing/test_for_n6_manage_component-inner.csr
N6Lib/n6lib/tests/certs_and_requests_for_testing/test_for_n6_manage_component-outer.csr
N6Lib/n6lib/tests/certs_and_requests_for_testing/test_for_n6_manage_private.key
```

If you are using docker you can generate test data for the n6manage component by executing the command:

```
docker-compose run worker bash -c  "mysql -h mysql -u root -ppassword --database=auth_db  < /home/dataman/n6/etc/mysql/insertdb/insert_data_auth_db.sql"
```

If you are going to generate your certificates, you should replace the above examples. If you already have
generated certificates, you can skip to the Use Cases section.

## Generating client/component CSRs for signing with n6manage and adding to AuthAPI

The client generates and sends CSR to CERT where certificates are signed with the appropriate CA.

Temporary directory with generated certificates: `N6Lib/n6lib/tests/certs_and_requests_for_testing`.

### Generating an RSA private key (by the client)

```
$ openssl genrsa -out private.key
```

### Generating CSR

**O**: Organization ID (based on a domain e.g. example.com)

**CN**: User ID (based on an email, e.g. user@example.com)

#### Creating CSR for an application user - client

```
$ openssl req -new -key private.key -out client.csr -subj '/CN=user@example.com/O=example.com/C=PL'
```

#### Creating CSR for an application user - administrator

```
$ openssl req -new -key private.key -out admin.csr -subj '/CN=admin@example.com/O=example.com/C=PL/OU=n6admins'
```

#### Create CSR for an internal component

```
$ openssl req -new -key private.key -out component-inner.csr -subj '/CN=component.inner.example.com/O=example.com/C=PL/OU=n6components'
```

!!! note

    **CN** may not contain the domain part.

### Creating CSR an external component

```
$ openssl req -new -key private.key -out component-outer.csr -subj '/CN=component.outer.example.com/O=example.com/C=PL/OU=Internal Unit'
```

### Creating administrator user "ads-adm@example.com" with rights to use n6manage command

For our needs, we will use already generated user certificates located in the tests directory:`N6Lib/n6lib/tests/certs_and_requests_for_testing`.

```
N6Lib/n6lib/tests/certs_and_requests_for_testing/ads-adm-cert---n6-service-ca-00000000000000000018.pem
```

You can generate a new certificate for the "ads-adm@example.com" user:

```
$ cd N6Lib/n6lib/tests/certs_and_requests_for_testing
$ ./gen-cert.sh ads-adm n6-service-ca 00000000000000000018 /CN=ads-adm@example.com/O=example.com/OU=n6admins
```

## n6manage configuration

Edit configuration files:

1.`.n6/09_auth_db.conf`

```
[auth_db]
# CA that will sign the certificates: `ca-cert-n6-service-ca`
ssl_cacert = /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing/ca-cert-n6-service-ca.pem
# Choose the user account that will have access to AuthDB (in this case it is the ads-adm-cert client)
ssl_cert = /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing/ads-adm-cert---n6-service-ca-00000000000000000018.pem
ssl_key = /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing/ads-adm-key---n6-service-ca-00000000000000000018.pem
```

2.`.n6/09_manage.conf`

```
[manage_api]
ca_key_root = /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing/ca-key-root.pem
ca_key_n6_client_ca = /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing/ca-key-n6-client-ca.pem
ca_key_n6_service_ca = /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing/ca-key-n6-service-ca.pem
internal_o_regex_pattern = \Aexample.com\Z
server_component_ou_regex_pattern = \AInternal Unit\Z
```

## AuthDB configuration

Configuration consists in filling the AuthDB database with data from the fields of individual tabs
in the Admin panel: `https://localhost:4444`.

### Editing`System Group` tab

- admins
- clients

### Editing `C A Cert` tab

```
* create `root`
* Ca Label: `root`
* Certificate: content of ca-cert-root.pem
* SSl Config: none
* Profile: can be left blank
* Children Ca: can be left blank
* Certs: can be left blank
* Parent Ca: can be left blank
* Remaining fields from the certificate: `ca-cert-root.pem`
```

```
* create `n6-client-ca`
* description: CA for signing user certificates
* Ca Label: n6-client-ca
* Certificate: content of `ca-cert-n6-client-ca.pem`
* Ssl Config: contents of `ca-config-n6-client-ca.cnf`
* Profile: client
* Parent CA: `CaCert "root"`
```

```
* create `n6-service-ca`
* description: CA for signing administrator certificates and components
* Ca Label: `n6-service-ca`
* Certificate: contents of `ca-cert-n6-service-ca.pem`
* Ssl Config: contents of `ca-config-n6-service-ca.cnf`
* Profile: `service`
* Parent CA: `CaCert "root"`
```

#### Adding `ads-adm` user

```
* Login: `ads-adm@example.com`
* Password: no password required
* Org: `example.com`
* System groups: `admins`
```

### Editing `Cert` tab

#### Adding `ads-adm` user certificate

```
* Ca Cert: `CaCert "n6-service-ca"`
* Hex: 00000000000000000018 (this is the field from the name of the certificate (20 characters))
* Owner: `ads-adm@example.com`
* Certificate: content of `ads-adm-cert---n6-service-ca-00000000000000000018.pem`
* Csr: content of `ads-adm-csr---n6-service-ca-00000000000000000018.pem`
* Valid From: 2020-08-20 08:48:00
* Expires On: 2028-11-06 10:46:00
* Created On: 2020-08-25 08:48:00
```

# Use cases

## Creating application user certificate - client

We execute the commands from the location of the directory where we have generated user certificates:
`N6Lib/n6lib/tests/certs_and_requests_for_testing`

```
$ source /home/dataman/env/bin/activate
$ cd /home/dataman/n6/N6Lib/n6lib/tests/certs_and_requests_for_testing
$ n6manage make-cert -a -d . n6-client-ca test_for_n6_manage_client.csr
```

The test result is a generated and signed user certificate `user@example.com`.
The certificate has a **serial hex**, which is in the name of the certificate file (20 characters)
e.g. `n6-client-ca-10944d82c1845eb266ad-user-example.com.pem`.
A new user has been created in the AuthDB database along with the assigned certificate.

## Creating application user certificate - administrator

```
$ n6manage make-cert -a -d . n6-service-ca test_for_n6_manage_admin.csr
```

A certificate will be the result of the test. The certificate file name will contain the identification number - **serial hex** (20 characters).
This number can also be found in the AuthDB database certificate.
A new user has been created in the AuthDB database along with the associated certificate.

## Creating internal component certificate

```
$ n6manage make-cert -d . n6-service-ca test_for_n6_manage_component-inner.csr
```

You must add a component to the component tab first.

The component name: `component.inner.example.com`.

## Creating external component certificate

```
$ n6manage make-cert -a -d . -s component.outer.example.com n6-service-ca test_for_n6_manage_component-outer.csr
```

The OU (Organizational Unit) field of the external component certificate must match the regex fixed
pattern i.e. the value of the `server_component_ou_regex_pattern` option
in the `manage_api` section of the configuration file (`.n6/09_manage.conf`).

## Adding previously created certificate

### Internal component

```
$ n6manage add-cert n6-service-ca component-internal-cert---n6-service-ca-ce0c519c49fd5659271d.pem 2020-10-02T14:31Z
```

You have to create a component named `component-four` in advance.

### External Component

```
$ n6manage add-cert -a -s my.web.server n6-service-ca serv-comp-cert---n6-service-ca-00000000000000123456.pem 2020-10-02T14:31Z
```

## Certificate revocation

### Customer

```
$ n6manage revoke-cert -d . n6-client-ca c55fd65ffe0671c4ba19 'What a bad client certificate!'`
```

Before that, you should add a ready certificate using the command below:

```
$ n6manage add-cert -a n6-client-ca other-revocation-cert---n6-client-ca-c55fd65ffe0671c4ba19.pem 2020-10-02T14:31Z
```

### Service

```
$ n6manage revoke-cert -d . n6-service-ca 00000000000000123456 'What a bad service certificate!'
```

### Downloading certificate

```
$ n6manage dump-cert -d . n6-client-ca dd94bb25b91c23098523
```

### Downloading list of withdrawn certificates (CRL)

```
$ n6manage dump-crl n6-service-ca
```

### Listing CA certificates stored in Auth DB

```
$ n6manage list-ca
```

## Parameters available to `n6manage`:

> 'list-ca', 'add-cert', 'make-cert', 'revoke-cert', 'dump-cert', 'dump-crl'.

```
$ n6manage <PARAMETER>
```

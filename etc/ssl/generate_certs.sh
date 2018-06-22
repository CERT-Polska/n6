#!/bin/bash

set -ex

DAYS=1365
CN=login@example.com
ORG=example.com
OPENSSL_CNF=openssl.cnf

mkdir -p n6-CA/certs n6-CA/private
touch n6-CA/index.txt
touch n6-CA/index.txt.attr
echo 10 > n6-CA/serial

openssl req -x509 -config $OPENSSL_CNF -newkey rsa:2048 -days $DAYS -out n6-CA/cacert.pem -outform PEM -subj /CN=n6-CA/ -nodes


openssl genrsa -out key.pem 2048
openssl req -new -key key.pem -out req.csr -outform PEM -subj /CN=$CN/O=$ORG/ -nodes
openssl ca -config $OPENSSL_CNF -in req.csr -out cert.pem -days $DAYS -notext -batch -extensions server_and_client_ca_extensions


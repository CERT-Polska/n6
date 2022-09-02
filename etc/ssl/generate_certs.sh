#!/bin/bash

set -ex

DAYS=1365
CN=login@example.com
ORG=example.com
OPENSSL_CNF=openssl.cnf

# increment the serial number if the certificate with the same serial
# number already exists
echo 12 > n6-CA/serial

openssl genrsa -out key.pem 2048
openssl req -new -key key.pem -out req.csr -outform PEM -subj /CN=$CN/O=$ORG/ -nodes
openssl ca -config $OPENSSL_CNF -in req.csr -out cert.pem -days $DAYS -notext -batch -extensions server_and_client_ca_extensions

#!/bin/bash

set -ex

DAYS=1365
CN=login@example.com
ORG=example.com
OPENSSL_CNF=openssl.cnf

# increment the serial number if the certificate with the same serial
# number already exists
echo 12 > generated_certs/n6-CA/serial

openssl genrsa -out generated_certs/key.pem 2048
openssl req -new -key generated_certs/key.pem -out generated_certs/req.csr -outform PEM -subj /CN=$CN/O=$ORG/ -nodes
openssl ca -config $OPENSSL_CNF -in generated_certs/req.csr -out generated_certs/cert.pem -days $DAYS -notext -batch -extensions server_and_client_ca_extensions

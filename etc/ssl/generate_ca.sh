#!/bin/bash

set -ex

DAYS=1365
OPENSSL_CNF=openssl.cnf

mkdir -p n6-CA/certs n6-CA/private
touch n6-CA/index.txt
touch n6-CA/index.txt.attr

# use the command below to generate a new CA file
openssl req -x509 -config $OPENSSL_CNF -newkey rsa:2048 -days $DAYS -out n6-CA/cacert.pem -outform PEM -subj /CN=n6-CA/ -nodes

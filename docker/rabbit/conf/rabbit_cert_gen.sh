#!/bin/bash

set -ex

DAYS=1365
PASS1=pass
PASS2=pass
home=`pwd`/cert
cn_rabbit=rabbit
cn_n6=test

# CA
mkdir -p $home/testca/certs $home/testca/private $home/server $home/client
cp openssl.cnf $home/testca
chmod 700 $home/testca/private
echo 01 > $home/testca/serial
touch $home/testca/index.txt $home/testca/index.txt.attr
cd $home/testca
openssl req -x509 -config openssl.cnf -newkey rsa:2048 -days $DAYS -out cacert.pem -outform PEM -subj /CN=MyTestCA/ -nodes
openssl x509 -in cacert.pem -out cacert.cer -outform DER

# rabbit
cd $home
openssl genrsa -out server/key.pem 2048
openssl req -new -key server/key.pem -out server/req.pem -outform PEM -subj /CN=$cn_rabbit/O=MyOrg/ -nodes
cd $home/testca
openssl ca -config openssl.cnf -in ../server/req.pem -out ../server/cert.pem -notext -batch -extensions server_ca_extensions

# n6
cd $home/client
#openssl pkcs12 -export -out keycert.p12 -in cert.pem -inkey key.pem -passout pass:$PASS1
openssl genrsa -out key.pem 2048
openssl req -new -key key.pem -out req.pem -outform PEM -subj /CN=$cn_n6/O=n6component/ -nodes
cd $home/testca
openssl ca -config openssl.cnf -in ../client/req.pem -out ../client/cert.pem -notext -batch -extensions client_ca_extensions

#!/bin/bash

set -e

cmd="$1"
tests="$2"

if [ $# -eq 0 ]
  then
    echo "No arguments supplied"
fi

until rabbitmqadmin --ssl --ssl-disable-hostname-verification \
             --ssl-ca-cert-file=/root/n6/docker/rabbit/certs/n6-CA/cacert.pem \
             --host=rabbit \
             --port=15671 \
             --username=login@example.com \
             --password=n6component \
             --format='bash' \
             list users | grep login@example.com > /dev/null 2>&1; do
  >&2 echo "rabbitmqadmin 'list users' is unavailable - sleeping. Please wait..."
  sleep 4
done
>&2 echo "rabbit is ready to work!"

until echo 'show databases;' | mysql -h mysql -u root -ppassword | grep n6 > /dev/null 2>&1; do
  >&2 echo "mysql is unavailable - sleeping. Please wait..."
  sleep 2
done
>&2 echo "mysq is up!"

until echo 'db.stats()' | mongo n6 -u admin -p admin1 --host mongo | grep n6 > /dev/null 2>&1; do
  >&2 echo "mongo is unavailable - sleeping. Please wait..."
  sleep 2
done
>&2 echo "mongo is ready to work - executing command"

exec $cmd "$tests"
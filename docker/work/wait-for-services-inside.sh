#!/bin/bash

set -e
counter_limit=30

# check rabbit availability
counter_rabbit=1
until rabbitmqadmin --ssl --ssl-disable-hostname-verification \
    --ssl-ca-cert-file=/root/certs/n6-CA/cacert.pem \
    --host=rabbit --port=15671 list users 2>&1 | grep login@example.com > /dev/null 2>&1; do
  >&2 echo "rabbitmqadmin 'list users' is unavailable - sleeping $counter_rabbit/$counter_limit. Waiting for rabbit ..."
  ((counter_rabbit++))
  sleep 4
  if [[ counter_rabbit -gt $counter_limit ]]; then
    exit 1
  fi
done
>&2 echo "rabbit 'list users' is up!"

# check mysql availability
counter_mysql=1
until echo 'show databases;' | mysql -h mysql -u root -ppassword 2>&1 | grep n6 > /dev/null 2>&1; do
  >&2 echo "mysql is unavailable - sleeping $counter_mysql/$counter_limit. Waiting for mysql ..."
  ((counter_mysql++))
  sleep 4
    if [[ counter_mysql -gt $counter_limit ]]; then
    exit 1
  fi
done
>&2 echo "mysq is up!"

# check mongo availability
counter_mongo=1
until mongo n6 --host mongo -u admin -p password --eval "db.stats()" > /dev/null 2>&1; do
  >&2 echo counter_mongo "mongo is unavailable - sleeping $counter_mongo/$counter_limit. Waiting for mongo ..."
  ((counter_mongo++))
  sleep 4
  if [[ counter_mongo -gt $counter_limit ]]; then
    >&2 echo "mongo is unavailable - sleeping $counter_mongo/10. Waiting for mongo ..."
  exit 1
  fi
done
>&2 echo "mongo is ready to work - executing command"
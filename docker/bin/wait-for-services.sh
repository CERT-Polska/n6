#!/bin/bash

set -e
counter_limit=90
counter_rabbit=1
counter_mysql=1
counter_redis=1
counter_mailhog=1

# check rabbit availability
until rabbitmqadmin --ssl --ssl-disable-hostname-verification \
    --ssl-ca-cert-file=/home/dataman/certs/n6-CA/cacert.pem \
    --host=rabbit --port=15671 list users | grep login@example.com 1>/dev/null; do
  >&2 echo "rabbitmqadmin 'list users' is unavailable - sleeping $counter_rabbit/$counter_limit. Waiting for rabbit ..."
  ((counter_rabbit++))
  sleep 4
  if [[ counter_rabbit -gt $counter_limit ]]; then
    >&2 echo "RabbitMQ is still unavailable. Exiting ..."
    exit 1
  fi
done
>&2 echo "RabbitMQ 'list users' is up!"

# check mysql availability
until echo 'show databases;' | mysql -h mysql -u root -ppassword | grep n6 1>/dev/null; do
  >&2 echo "MySQL is unavailable - sleeping $counter_mysql/$counter_limit. Waiting for mysql ..."
  ((counter_mysql++))
  sleep 4
  if [[ counter_mysql -gt $counter_limit ]]; then
    >&2 echo "MySQL is still unavailable. Exiting ..."
    exit 1
  fi
done
>&2 echo "MySQL is up!"

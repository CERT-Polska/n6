#!/bin/bash

counter_limit_restart=160
counter_limit_exit=260

# checking service rabbit availability ouside container
counter_rabbit=1
until docker-compose --file test_N6Itests/docker-non-pub/docker-compose.yml exec rabbit rabbitmqctl wait /var/lib/rabbitmq/mnesia/rabbit\@rabbit.pid >&2; do
  echo "Inside checker: rabbitmqadmin unavailable - sleeping $counter_rabbit/$counter_limit_restart. Waiting for rabbit..."
  counter_rabbit=$((counter_rabbit+1))
  sleep 1
  if [ $counter_rabbit -gt $counter_limit_restart ]; then
    >&2 echo "Rabbit is restarting..."
    docker-compose --file test_N6Itests/docker-non-pub/docker-compose.yml restart rabbit
    break
  fi
done

# checking service database mariadb is available ouside container
counter_mysql=1
until docker-compose --file test_N6Itests/docker-non-pub/docker-compose.yml logs mysql | grep "mysqld: ready for connections." > /dev/null 2>&1; do
  >&2 echo "Inside checker: database engine unavailable - sleeping $counter_mysql/$counter_limit_restart. Waiting for mysql..."
  counter_mysql=$((counter_mysql+1))
  sleep 1
  if [ $counter_mysql -gt $counter_limit_restart ]; then
    >&2 echo "Mysql is restarting..."
    docker restart mysql

    counter_mysql=$((counter_mysql-1))
    until docker-compose --file test_N6Itests/docker-non-pub/docker-compose.yml logs --tail=30 mysql | grep "mysqld: ready for connections." >/dev/null 2>&1; do
        counter_mysql=$((counter_mysql+1))
        echo "still unavailable...- sleeping $counter_mysql/$counter_limit_exit. Waiting for mysql..."
        sleep 1
        if [ $counter_mysql -eq $counter_limit_exit ]; then
        exit 1
        fi
    done
    break
  fi
done

>&2 echo "Continue starting services"

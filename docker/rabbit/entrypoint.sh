#!/bin/bash

echo "Starting RabbitMQ..."

(
  count=0;
  # Execute list_users until service is up and running
  until timeout 5 rabbitmqctl list_users >/dev/null 2>&1 || (( count++ >= 60 )); \
  do sleep 1; done; \
  if rabbitmqctl list_users >/dev/null 2>&1
  then
    # Create Rabbitmq user
    rabbitmqctl add_user $RABBITMQ_DEFAULT_USER $RABBITMQ_DEFAULT_PASS
    rabbitmqctl set_user_tags $RABBITMQ_DEFAULT_USER administrator
    rabbitmqctl set_permissions -p / $RABBITMQ_DEFAULT_USER ".*" ".*" ".*"
    rabbitmqctl add_user $RABBITMQ_USER $RABBITMQ_PASSWORD
    rabbitmqctl set_user_tags $RABBITMQ_USER administrator
    rabbitmqctl set_permissions -p / $RABBITMQ_USER ".*" ".*" ".*"
    rabbitmqctl set_policy synchronisation "" '{"ha-mode":"all","ha-sync-mode":"automatic"}'
    echo "*** User '$RABBITMQ_USER' with password '$RABBITMQ_PASSWORD' completed. ***"
    echo "*** Log in the WebUI at port 15671 ***"
  fi
) & rabbitmq-server $@

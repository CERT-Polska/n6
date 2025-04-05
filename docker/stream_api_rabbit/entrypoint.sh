#!/bin/bash

echo "Starting RabbitMQ..."

(
  count=0;
  # Execute list_users until service is up and running
  until timeout 5 rabbitmqctl list_users >/dev/null 2>&1 || (( count++ >= 60 )); \
  do sleep 1; done; \
  if rabbitmqctl list_users >/dev/null 2>&1
  then
    rabbitmqctl add_user $RABBITMQ_USER $RABBITMQ_PASSWORD
    rabbitmqctl set_user_tags $RABBITMQ_USER administrator
    rabbitmqctl set_permissions -p / $RABBITMQ_USER ".*" ".*" ".*"
    rabbitmqctl set_parameter federation-upstream example_upstream "{\"uri\":\"amqp://$RABBITMQ_FED_USER:$RABBITMQ_PASSWORD@rabbit\",\"expires\":3600000,\"ack-mode\":\"on-confirm\",\"prefetch-count\":20}"
    rabbitmqctl set_policy p-event "^event" \
    '{"federation-upstream-set":"all"}'
    echo "*** User '$RABBITMQ_USER' with password '$RABBITMQ_PASSWORD' completed. ***"
    echo "*** Log in the WebUI at port 15671 ***"
  fi
) & rabbitmq-server $@

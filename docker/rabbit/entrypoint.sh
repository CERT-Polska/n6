#!/bin/sh

set -x

# Create Rabbitmq user
( echo "Starting RabbitMQ..." ; sleep 5 ;\
rabbitmqctl add_user $RABBITMQ_USER $RABBITMQ_PASSWORD ;\
rabbitmqctl set_user_tags $RABBITMQ_USER administrator ;\
rabbitmqctl set_permissions -p / $RABBITMQ_USER ".*" ".*" ".*" ;\
rabbitmqctl set_policy synchronisation "" '{"ha-mode":"all","ha-sync-mode":"automatic"}' ;\
rabbitmq-plugins enable rabbitmq_management rabbitmq_management_agent rabbitmq_auth_mechanism_ssl rabbitmq_federation rabbitmq_federation_management rabbitmq_shovel rabbitmq_shovel_management ; \
echo "*** User '$RABBITMQ_USER' with password '$RABBITMQ_PASSWORD' completed. ***" ; \
echo "*** Log in the WebUI at port 15671 ***") & rabbitmq-server $@
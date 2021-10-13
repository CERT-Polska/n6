ARG DOCKER_IMAGE=rabbitmq:3.8-management
FROM $DOCKER_IMAGE

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

RUN rabbitmq-plugins enable --offline \
    rabbitmq_management \
    rabbitmq_management_agent \
    rabbitmq_auth_mechanism_ssl \
    rabbitmq_federation \
    rabbitmq_federation_management \
    rabbitmq_shovel \
    rabbitmq_shovel_management

COPY etc/rabbitmq/conf/rabbitmq.conf /etc/rabbitmq/rabbitmq.conf
ADD docker/rabbit/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

EXPOSE 5671 15671 15672
CMD ["/entrypoint.sh"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD rabbitmq-diagnostics ping -q || exit 1

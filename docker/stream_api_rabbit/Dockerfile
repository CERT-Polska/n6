ARG DOCKER_IMAGE=rabbitmq:3.8-management
FROM $DOCKER_IMAGE

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

RUN rabbitmq-plugins enable --offline \
    rabbitmq_management \
    rabbitmq_management_agent \
    rabbitmq_auth_backend_http \
    rabbitmq_auth_mechanism_ssl \
    rabbitmq_federation \
    rabbitmq_federation_management \
    rabbitmq_shovel \
    rabbitmq_shovel_management \
    rabbitmq_stomp \
    rabbitmq_web_dispatch

COPY etc/streamapi/rabbitmq/rabbitmq.conf /etc/rabbitmq/rabbitmq.conf
COPY etc/streamapi/rabbitmq/advanced.config /etc/rabbitmq/advanced.config
COPY etc/ssl/generated_certs/ /etc/rabbitmq/certs/

ADD docker/stream_api_rabbit/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

EXPOSE 15671 5672 61614
CMD ["/entrypoint.sh"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD rabbitmq-diagnostics ping -q || exit 1

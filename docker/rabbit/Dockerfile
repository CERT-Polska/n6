FROM rabbitmq:3.6.9-management

# interactive mode
ENV TERM xterm
ENV RABBITMQ_USER login@example.com
ENV RABBITMQ_PASSWORD n6component

ADD docker/rabbit/conf/rabbitmq.config /etc/rabbitmq/rabbitmq.config
ADD docker/rabbit/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

EXPOSE 5671 15671
CMD ["/entrypoint.sh"]
FROM mongo:2.6.9

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

ENV AUTH yes
ENV JOURNALING no
# Setting apt tool will automatically retry if a package download fails
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries

ADD docker/mongo/entrypoint.sh /entrypoint.sh
ADD docker/mongo/set_mongodb_password.sh /set_mongodb_password.sh
RUN set -ex; \
    chmod a+x /entrypoint.sh \
              /set_mongodb_password.sh

CMD ["/entrypoint.sh"]

EXPOSE 27017
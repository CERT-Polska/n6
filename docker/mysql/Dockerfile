ARG DOCKER_IMAGE=mariadb:10.3-bionic
FROM $DOCKER_IMAGE

# MariaDB image with TokuDB engine
# solution how to install taken from:
# https://github.com/docker-library/mariadb/issues/219#issuecomment-456909306

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
    apt-get install -y \
        mariadb-plugin-tokudb \
        libjemalloc1


RUN ["/bin/bash", "-c", "rm -rf /etc/mysql/conf.d/*"]
COPY ./etc/mysql/conf.d/mariadb.cnf /etc/mysql/conf.d/mariadb.cnf
RUN ["/bin/chmod", "a-w", "/etc/mysql/conf.d"]
RUN ["/bin/chmod", "a-w", "/etc/mysql/conf.d/mariadb.cnf"]
COPY ./etc/mysql/initdb /docker-entrypoint-initdb.d 

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.1

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD mysqladmin -u $MYSQL_USERNAME -p$MYSQL_ROOT_PASSWORD ping && \
    echo 'show databases' | mysql n6 -h mysql -u $MYSQL_USERNAME -p$MYSQL_ROOT_PASSWORD | grep n6 || exit 1

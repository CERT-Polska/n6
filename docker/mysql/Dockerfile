ARG DOCKER_IMAGE=mariadb:10.11
FROM $DOCKER_IMAGE

ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
	apt-get install -y \
	mariadb-plugin-rocksdb && \
    rm -rf /var/cache/apt/lists/*

RUN ["/bin/bash", "-c", "rm -rf /etc/mysql/conf.d/*"]
COPY ./etc/mysql/conf.d/mariadb.cnf /etc/mysql/conf.d/mariadb.cnf
RUN ["/bin/chmod", "a-w", "/etc/mysql/conf.d"]
RUN ["/bin/chmod", "a-w", "/etc/mysql/conf.d/mariadb.cnf"]
COPY ./etc/mysql/initdb /docker-entrypoint-initdb.d 


HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD mysqladmin -u $MYSQL_USERNAME -p$MYSQL_ROOT_PASSWORD ping && \
    echo 'show databases' | mysql n6 -h mysql -u $MYSQL_USERNAME -p$MYSQL_ROOT_PASSWORD | grep n6 || exit 1

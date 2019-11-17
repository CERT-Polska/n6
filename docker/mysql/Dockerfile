FROM mariadb:10.4

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD mysqladmin -u $MYSQL_USERNAME -p$MYSQL_ROOT_PASSWORD ping && \
    echo 'show databases' | mysql n6 -h mysql -u $MYSQL_USERNAME -p$MYSQL_ROOT_PASSWORD | grep n6 || exit 1

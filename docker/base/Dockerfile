FROM debian:buster-slim

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

ARG use-proxy
ARG apt-proxy-nask

RUN \
    # install base dependencies
    echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries; \
    # server proxy for apt available only inside NASK
    if [ "${use-proxy}" = "true" ]; then \
        echo 'Acquire::http { Proxy "${apt-proxy-nask}"; };' > /etc/apt/apt.conf.d/90proxy; \
    fi; \
    apt-get update && \
    apt-get install -y \
        apache2 \
        build-essential \
        curl \
        default-libmysqlclient-dev \
        iputils-ping \
        ldap-utils \
        libapache2-mod-wsgi \
        libattr1-dev \
        libcurl4-openssl-dev \
        libffi-dev \
        libfuse-dev \
        libgeoip1 \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        libyajl2 \
        nodejs \
        npm \
        python2.7-dev \
        python-ldap \
        python-mysqldb \
        python-virtualenv \
        rsyslog \
        ssh \
        sudo \
        supervisor \
        swig \
        wget && \
    npm install -g npm@latest && \
    npm install node-sass && \
    sed '/st_mysql_options options;/a unsigned int reconnect;' /usr/include/mysql/mysql.h -i.bkp; \
    bash -c "echo 'ServerName localhost' >> /etc/apache2/apache2.conf"; \
    # create dataman user
    groupadd -g 1000 dataman && \
    useradd -rm \
            -d /home/dataman \
            -s /bin/bash \
            -p '' \
            -g dataman \
            -G root,sudo,www-data \
            -u 1000 dataman && \
    echo "dataman	ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers; \
    # n6 directory structure
    bash -c "mkdir -p /etc/{n6,ssh} /home/dataman/{.n6,logs,tmp} /home/dataman/n6/.python-eggs /var/www /etc/apache2/sites-available" && \
    chown -R dataman:dataman \
        /etc/n6 /home/dataman/ /var/www /etc/ssh/ /etc/apache2/sites-available && \
    chmod -R 755 \
        /etc/n6 /home/dataman/ /var/www /etc/ssh/ /etc/apache2/sites-available; \
    # RabbitMQ client
    wget https://raw.githubusercontent.com/rabbitmq/rabbitmq-management/v3.8.x/bin/rabbitmqadmin -P /usr/local/bin/ && \
    chown dataman:dataman /usr/local/bin/rabbitmqadmin && \
    chmod +x /usr/local/bin/rabbitmqadmin; \
    # Mongo & MySQL client
    wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | apt-key add - && \
    echo "deb http://repo.mongodb.org/apt/debian buster/mongodb-org/4.2 main" | tee /etc/apt/sources.list.d/mongodb-org.list && \
    apt-get update && \
    apt-get install -y \
        mongodb-org \
        default-mysql-client && \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*;

USER dataman
WORKDIR /home/dataman

COPY --chown=dataman:dataman . n6

RUN set -ex; \
    # server proxy for pip available only inside NASK
    if [ "${use-proxy}" = "true" ]; then \
        mkdir -p /home/dataman/.config/pip/; \
        cp n6/test_N6Itests/docker-non-pub/etc/pip/pip.conf /home/dataman/.config/pip/; \
        cp n6/test_N6Itests/docker-non-pub/etc/pip/.pydistutils.cfg /home/dataman/; \
    fi; \
    # copy certs
    cp -rf n6/etc/ssl/generated_certs certs; \
    # create virtualenv
    virtualenv  --no-setuptools env; \
    . env/bin/activate; \
    pip install --upgrade pip -i https://pypi.python.org/simple/; \
    pip install --upgrade 'setuptools<45.0.0'; \
    # install tools for n6 tests
    pip install --no-cache-dir \
        nose \
        timeout_decorator \
        puka \
        pycurl \
        pylint==1.9.2 \
        pyrabbit \
        unittest-xml-reporting; \
    # install n6 dependencies
    cd n6 \
        && pip install --no-cache-dir -r N6Lib/requirements \
        && pip install --no-cache-dir -r N6Push/requirements \
        && pip install --no-cache-dir -r N6SDK/requirements; \
    # install portal js dependencies
    cd /home/dataman/n6/N6Portal/gui \
        && npm set progress=false \
        && npm config set depth 0 \
        && npm install \
        && tar -zcf ~/node_modules.tar.gz node_modules \
        && rm -rf node_modules; \
    # entrypoint
    cp ~/n6/docker/base/entrypoint.sh ~/; \
    chmod a+x /home/dataman/entrypoint.sh;


ENTRYPOINT ["/home/dataman/entrypoint.sh"]

# Command to build:
# docker build -t n6_base -f docker/base/Dockerfile .

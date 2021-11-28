ARG DOCKER_IMAGE=debian:bullseye-slim
FROM $DOCKER_IMAGE

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

ARG use-proxy
ARG apt-proxy-nask

RUN \
    # install base dependencies
    echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries; \
    # apt-related: optional custom (our-organization-specific) proxy
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
        libapache2-mod-wsgi-py3 \
        libattr1-dev \
        libcurl4-openssl-dev \
        libffi-dev \
        libfuse-dev \
        libgeoip1 \
        libsasl2-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        libyajl2 \
        nodejs \
        npm \
        python2.7 \
        python2.7-dev \
        python3 \
        python3-dev \
        python3-venv \
        virtualenv \
        redis-tools \
        rsyslog \
        ssh \
        sudo \
        supervisor \
        swig \
        wget \
        zlib1g-dev \
        libncurses5-dev \
        libgdbm-dev \
        libnss3-dev \
        libreadline-dev \
        libsqlite3-dev \
        libbz2-dev && \
    npm install -g npm@latest && \
    npm install node-sass && \
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
    bash -c "mkdir -p /etc/ssh /home/dataman/{.n6,logs,tmp} /var/www /etc/apache2/sites-available /home/dataman/.cache/n6/n6api/{python-eggs,python3k-eggs} /home/dataman/.cache/n6/n6portal/{python-eggs,python3k-eggs} /home/dataman/.cache/n6/n6adminpanel/{python-eggs,python3k-eggs}" && \
    chown -R dataman:dataman \
        /home/dataman/ /var/www /etc/ssh/ /etc/apache2/sites-available && \
    chmod -R 755 \
        /home/dataman/ /var/www /etc/ssh/ /etc/apache2/sites-available; \
    chown -R dataman:www-data \
        /home/dataman/.cache/n6/n6api/python-eggs /home/dataman/.cache/n6/n6api/python3k-eggs \
        /home/dataman/.cache/n6/n6portal/python-eggs /home/dataman/.cache/n6/n6portal/python3k-eggs \
        /home/dataman/.cache/n6/n6adminpanel/python-eggs /home/dataman/.cache/n6/n6adminpanel/python3k-eggs && \
    chmod -R 755 \
        /home/dataman/.cache/n6/n6api/python-eggs /home/dataman/.cache/n6/n6api/python3k-eggs \
        /home/dataman/.cache/n6/n6portal/python-eggs /home/dataman/.cache/n6/n6portal/python3k-eggs \
        /home/dataman/.cache/n6/n6adminpanel/python-eggs /home/dataman/.cache/n6/n6adminpanel/python3k-eggs; \
    # RabbitMQ client
    wget https://raw.githubusercontent.com/rabbitmq/rabbitmq-management/v3.8.x/bin/rabbitmqadmin -P /usr/local/bin/ && \
    sed -i '1i#!/usr/bin/env python\n' /usr/local/bin/rabbitmqadmin && \
    chown dataman:dataman /usr/local/bin/rabbitmqadmin && \
    chmod +x /usr/local/bin/rabbitmqadmin; \
    # Mongo & MySQL client
    wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | apt-key add - && \
    echo "deb http://repo.mongodb.org/apt/debian buster/mongodb-org/4.2 main" | tee /etc/apt/sources.list.d/mongodb-org.list && \
    apt-get update && \
    apt-get install -y \
        mongodb-org-shell \
    default-mysql-client && \
    apt-get clean;

USER dataman
WORKDIR /home/dataman

COPY --chown=dataman:dataman . n6

RUN set -ex; \
    # pip-related: optional custom (our-organization-specific) configuration, including proxy
    if [ "${use-proxy}" = "true" ]; then \
        mkdir -p /home/dataman/.config/pip/; \
        cp n6/test_N6Itests/docker-non-pub/etc/pip/pip.conf /home/dataman/.config/pip/; \
        cp n6/test_N6Itests/docker-non-pub/etc/pip/.pydistutils.cfg /home/dataman/; \
    fi; \
    # copy certs
    cp -rf n6/etc/ssl/generated_certs certs; \
    # create virtualenv (n6)
    virtualenv --python=/usr/bin/python2.7 env; \
    . env/bin/activate; \
    pip install --upgrade pip -i https://pypi.python.org/simple/; \
    pip install --upgrade 'setuptools<45.0.0'; \
    pip install --upgrade wheel; \
    # workaround against crash during normal install of httplib2 (needed by some test tools...)
    wget https://files.pythonhosted.org/packages/92/92/478727070c62def583e645ceeba18e69df266bf78e11639bc787c2386421/httplib2-0.20.1.tar.gz; \
    tar xf httplib2-0.20.1.tar.gz; \
    rm httplib2-0.20.1.tar.gz; \
    cd httplib2-0.20.1; \
    python setup.py install; \
    cd ..; \
    rm -rf httplib2-0.20.1; \
    # install tools for n6 tests
    pip install --no-cache-dir \
        coverage==5.6b1 \
        nose \
        pytest==4.6.11 \
        pytest-cov==2.12.1 \
        timeout_decorator \
        puka \
        pycurl \
        pylint==1.9.2 \
        pylint-exit \
        pyrabbit \
        unittest_expander==0.3.1 \
        unittest-xml-reporting==2.5.2; \
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

RUN \
    # create virtualenv (n6)
    python3.9 -m venv env_py3k; \
    . env_py3k/bin/activate; \
    pip install --upgrade pip -i https://pypi.python.org/simple/; \
    pip install --upgrade setuptools; \
    pip install --upgrade wheel; \
    # install tools for n6 tests
    pip install --no-cache-dir \
        unittest_expander==0.3.1 \
        pytest==4.6.11 \
        pytest-cov==2.12.1 \
        coverage

RUN rm -rf /home/dataman/n6

ENTRYPOINT ["/home/dataman/entrypoint.sh"]

# Command to build:
# docker build -t n6_base -f docker/base/Dockerfile .

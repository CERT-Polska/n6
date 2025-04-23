ARG DOCKER_IMAGE=debian:bookworm-slim
FROM $DOCKER_IMAGE

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

ARG use-proxy
ARG apt-proxy-nask

# TODO: get rid of, no longer necessary, Python-2-related stuff...

RUN \
    apt-get update && \
    apt-get install -y \
        build-essential \
        ca-certificates \
        gnupg \
        curl;

RUN \
    # Create a directory for the new repository's keyring, if it doesn't exist
    mkdir -p /etc/apt/keyrings;

RUN \
    # Download the new repository's GPG key and save it in the keyring directory
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg;

RUN \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
    | tee /etc/apt/sources.list.d/nodesource.list;

# tmp fix for bug https://github.com/nodesource/distributions/issues/1601
RUN echo "Package: nodejs" >> /etc/apt/preferences.d/preferences; \
    echo "Pin: origin deb.nodesource.com" >> /etc/apt/preferences.d/preferences; \
    echo "Pin-Priority: 1001" >> /etc/apt/preferences.d/preferences;

RUN \
    apt-get update && \
    apt-get install -y nodejs;

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
        inotify-tools \
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
        libxml2-dev \
        libxslt1-dev \
        libyajl2 \
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
    npm install -g npm@9 && \
    npm install -g node-sass && \
    bash -c "echo 'ServerName localhost' >> /etc/apache2/apache2.conf";

# install libssl1.1.1 and libssl1.1.1-dev
RUN \
    wget --no-check-certificate http://security.debian.org/debian-security/pool/updates/main/o/openssl/libssl1.1_1.1.1w-0+deb11u2_amd64.deb; \
    wget --no-check-certificate http://security.debian.org/debian-security/pool/updates/main/o/openssl/libssl-dev_1.1.1w-0+deb11u2_amd64.deb

RUN \
    dpkg -i libssl1.1_1.1.1w-0+deb11u2_amd64.deb; \
    dpkg -i libssl-dev_1.1.1w-0+deb11u2_amd64.deb

RUN \
    # sudo apt-get install libssl-dev && \
    wget https://www.python.org/ftp/python/2.7.18/Python-2.7.18.tar.xz && \
    tar -xvf Python-2.7.18.tar.xz && \
    cd Python-2.7.18 && \
    ./configure && sudo make && sudo make install;

RUN \
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
    # MySQL client
    apt-get update && \
    apt-get install -y \
        default-mysql-client && \
    apt-get clean;

USER dataman
WORKDIR /home/dataman

COPY --chown=dataman:dataman . n6

RUN sudo python2.7 -m ensurepip --default-pip
RUN sudo pip install virtualenv

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
    virtualenv --python=python2.7 env; \
    . env/bin/activate; \
    pip install --upgrade pip -i https://pypi.python.org/simple/; \
    pip install --upgrade 'setuptools<45.0.0' wheel; \
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
        pyrabbit \
        unittest_expander==0.4.4 \
        unittest-xml-reporting==2.5.2; \
    # entrypoint
    cp ~/n6/docker/base/entrypoint.sh ~/; \
    cp ~/n6/docker/base/entrypoint_py2.sh ~/; \
    chmod a+x /home/dataman/entrypoint.sh; \
    chmod a+x /home/dataman/entrypoint_py2.sh;

RUN \
    # create virtualenv (n6)
    python3 -m venv env_py3k; \
    . env_py3k/bin/activate; \
    pip install --upgrade pip -i https://pypi.python.org/simple/; \
    # setuptools is locked as a part of a temporary workaround (TODO: fix it when #7792 is done + see: #8823)
    pip install --upgrade 'setuptools<68.0.0' wheel; \
    # install tools for n6 tests
    pip install --no-cache-dir \
        unittest_expander==0.4.4 \
        pytest==7.1.2 \
        pytest-cov==3.0.0 \
        coverage 

RUN rm -rf /home/dataman/n6

ENTRYPOINT ["/home/dataman/entrypoint.sh"]

# Command to build:
# docker build -t n6_base -f docker/base/Dockerfile .

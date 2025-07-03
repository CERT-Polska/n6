ARG DOCKER_IMAGE=debian:bookworm-slim
FROM $DOCKER_IMAGE

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive


RUN \
    # install base dependencies
    apt update && \
    apt install -y \
        build-essential \
        curl \
        gnupg2 \
        libattr1-dev \
        libgeoip1 \
        libsqlite3-dev \
        libssl-dev \
        libmariadb-dev \
        libbz2-dev \
        libffi-dev \
        libyajl2 \
        sudo \
        python3 \
        python3-dev \
        python3-venv \
        python3-stemmer \
        rsyslog \
        ssh \
        swig \
        systemd \
        virtualenv \
        wget \
        zlib1g-dev \
        apache2 \
        pip \
        libapache2-mod-wsgi-py3 \
        python3-virtualenv && \
        bash -c "echo 'ServerName localhost' >> /etc/apache2/apache2.conf";

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
    bash -c "mkdir -p  /home/dataman/.n6 /home/dataman/logs /etc/apache2/sites-available /home/dataman/apa_config/python-eggs /home/dataman/certs" && \
    chown -R dataman:dataman \
        /home/dataman/ /home/dataman/apa_config/ && \
    chmod -R 775 \
        /home/dataman/ /etc/apache2/sites-available; \
    chmod -R 777 \
        /home/dataman/apa_config/ /home/dataman/logs /home/dataman/apa_config/python-eggs; \
    # RabbitMQ client
    wget https://raw.githubusercontent.com/rabbitmq/rabbitmq-management/v3.8.x/bin/rabbitmqadmin -P /usr/local/bin/ && \
    sed -i '1i#!/usr/bin/env python\n' /usr/local/bin/rabbitmqadmin && \
    chown dataman:dataman /usr/local/bin/rabbitmqadmin && \
    chmod +x /usr/local/bin/rabbitmqadmin;

USER dataman
WORKDIR /home/dataman

COPY --chown=dataman:dataman . n6

RUN \
    # create virtualenv (n6datapipeline)
    python3 -m venv venv-n6datapipeline

RUN \
    # create virtualenv (n6brokerauthapi)
    python3 -m venv venv-n6brokerauthapi

# Install N6DataPipeline
RUN . /home/dataman/venv-n6datapipeline/bin/activate && \
    cd /home/dataman/n6 && \
    ./do_setup.py -u N6DataPipeline

# Copy n6 conf files
RUN cp -f /home/dataman/n6/etc/streamapi/n6/*.conf /home/dataman/.n6; \
    # copy certs
    cp -rf n6/etc/ssl/generated_certs/* certs; \
    # copy entrypoint and give appropariate permissions
    cp -f n6/docker/stream_api/entrypoint.sh .; \
    chmod a+x /home/dataman/entrypoint.sh;

# Install N6DataPipeline
RUN . /home/dataman/venv-n6brokerauthapi/bin/activate && \
    cd /home/dataman/n6 && \
    ./do_setup.py -u N6BrokerAuthApi

RUN cp -f /home/dataman/n6/etc/streamapi/apa_config/* /home/dataman/apa_config/; \
    cp -f /home/dataman/n6/etc/streamapi/apache2/* /etc/apache2/sites-available/;

USER root
RUN a2enmod wsgi && \
    a2ensite n6-brokerauthapi


USER dataman
WORKDIR /home/dataman
ENTRYPOINT ["/home/dataman/entrypoint.sh"]

# CMD sudo /usr/sbin/rsyslogd > /dev/null 2>&1 && \
#     service rsyslog start >/dev/null 2>&1 && \
#     sudo /usr/sbin/apache2ctl -D FOREGROUND
CMD ["sudo","/usr/sbin/apache2ctl", "-D", "FOREGROUND"]


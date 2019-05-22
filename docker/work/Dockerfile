FROM debian:stretch-slim

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

# additional apt settings
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries

# building environments
RUN set -ex; \
    apt-get update && apt-get install -y \
                      curl \
                      cron \
                      default-libmysqlclient-dev \
                      iputils-ping \
                      geoip-database \
                      libldap2-dev \
                      libsasl2-dev \
                      mysql-client \
                      python-pip \
                      python-dev \
                      libssl-dev \
                      libyajl2 \
                      swig \
                      python-setuptools \
                      supervisor \
                      rsyslog \
                      vim \
                      wget && \
                      apt-get clean


# Mongo client
RUN set -ex; \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 9DA31620334BD75D9DCB49F368818C72E52529D4 && \
    echo "deb http://repo.mongodb.org/apt/debian stretch/mongodb-org/4.0 main" | tee /etc/apt/sources.list.d/mongodb-org-4.0.list && \
    apt-get update && apt-get install -y \
                      mongodb-org-shell && \
                      apt-get clean

# speed up building image
WORKDIR /root/n6
COPY N6Lib/requirements N6Lib/requirements
COPY N6SDK/requirements N6SDK/requirements
RUN pip install -r N6Lib/requirements; \
    pip install -r N6SDK/requirements

# cloning repository
ADD . /root/n6/

# installation app
RUN set -ex; \
    ./do_setup.py N6Lib N6Core

# generate rabbit and web ssl certs
ADD docker/work/test_data/test-generate_certs.sh /root/certs/generate_certs.sh
RUN /root/certs/generate_certs.sh
ADD docker/rabbit/conf/rabbitmqadmin /usr/local/bin
RUN chmod a+x /usr/local/bin/rabbitmqadmin

# supervisor
ADD docker/work/test_data/test-supervisord.conf etc/supervisord/supervisord.conf
ADD docker/work/test_data/test-program_template.tmpl etc/supervisord/program_template.tmpl
ADD docker/work/test_data/test-n6aggregator.conf etc/supervisord/programs/n6aggregator.conf
ADD docker/work/test_data/test-n6archiveraw.conf etc/supervisord/programs/n6archiveraw.conf
ADD docker/work/test_data/test-n6comparator.conf etc/supervisord/programs/n6comparator.conf
ADD docker/work/test_data/test-n6enrich.conf etc/supervisord/programs/n6enrich.conf
ADD docker/work/test_data/test-n6filter.conf etc/supervisord/programs/n6filter.conf
ADD docker/work/test_data/test-n6recorder.conf etc/supervisord/programs/n6recorder.conf
RUN mkdir -p /root/supervisor/log /root/supervisor/programs
WORKDIR etc/supervisord
RUN python get_parsers_conf.py && \
    cp programs/*.conf /root/supervisor/programs/

# Rest tools
WORKDIR /root/n6
ADD docker/work/test_data/test-run_collectors /etc/cron.d/run_collectors
ADD docker/work/wait-for-services-inside.sh /wait-for-services.sh
RUN chmod +x /wait-for-services.sh
ADD docker/work/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "etc/supervisord/supervisord.conf"]
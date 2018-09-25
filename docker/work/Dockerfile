FROM debian:stretch-slim

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

# setting apt tool will automatically retry if a package download fails
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries

# building environments
RUN set -ex; \
    apt-get update && apt-get install -y \
                      curl \
                      cron \
                      default-libmysqlclient-dev \
                      iputils-ping \
                      ldap-utils \
                      libattr1-dev \
                      libffi-dev \
                      libfuse-dev \
                      libgeoip1 \
                      geoip-database \
                      libldap2-dev \
                      libsasl2-dev \
                      libssl-dev \
                      libxml2-dev \
                      libxslt1-dev \
                      libyajl2 \
                      mongodb-clients \
                      mysql-client \
                      pkg-config \
                      procps \
                      python-dev \
                      python-pastedeploy \
                      python-pip \
                      python-pycurl \
                      python-setuptools \
                      supervisor \
                      rsyslog \
                      swig \
                      vim \
                      wget && \
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

# rabbit access
ADD docker/rabbit/certs /root/certs
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
RUN chmod a+x /wait-for-services.sh
ADD docker/work/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "etc/supervisord/supervisord.conf"]
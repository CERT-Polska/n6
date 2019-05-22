FROM debian:stretch-slim

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

# additional apt settings
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries

# building environments
RUN set -ex; \
    apt-get update && apt-get install -y \
                                apache2 \
                                curl \
                                default-libmysqlclient-dev \
                                libapache2-mod-wsgi \
                                geoip-database \
                                libldap2-dev \
                                libsasl2-dev \
                                python \
                                python-pip \
                                python-setuptools \
                                python-virtualenv \
                                rsyslog \
                                python-pip \
                                python-dev \
                                libssl-dev \
                                libyajl2 \
                                swig \
                                sudo \
                                wget && \
                                apt-get clean

# adding the standard user with a blank password
RUN useradd -ms /bin/bash -p '' dataman
WORKDIR /home/dataman
# cloning the repository
ADD . /home/dataman/n6
ADD docker/web/test_data/test-n6-api.conf /etc/apache2/sites-available/n6-api.conf
ADD docker/web/test_data/test-n6-api.wsgi /home/dataman/n6/N6RestApi/n6-api.wsgi
ADD docker/web/test_data/test-production.ini /home/dataman/n6/N6RestApi/production.ini

# permissions
RUN chown -R dataman:dataman /home/dataman/n6 ;\
#    chown -R dataman:dataman /home/dataman/certs ;\
    usermod -a -G dataman www-data; \
    usermod -aG sudo dataman; \
    chown -R www-data:www-data /etc/apache2/sites-available/n6-api.conf; \
    chown -R dataman:dataman /home/dataman/n6/N6RestApi/n6-api.wsgi; \
    chown -R dataman:dataman /home/dataman/n6/N6RestApi/production.ini; \
    echo 'ServerName localhost' >> /etc/apache2/apache2.conf

# speed up building images
WORKDIR /home/dataman/n6
RUN pip install -r N6Lib/requirements; \
    pip install -r N6SDK/requirements

# installing n6 componenets
USER dataman
RUN sudo ./do_setup.py N6Core N6Lib N6SDK N6RestApi N6Portal N6AdminPanel;\
    yes | n6config

# n6adminpanel and n6portal
ADD docker/web/test_data/test-n6-adminpanel.conf /etc/apache2/sites-available/n6-adminpanel.conf
ADD docker/web/test_data/test-config.json N6Portal/gui/src/config/config.json
USER root
RUN set -ex; \
    curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash - ;\
    apt-get install -y nodejs && \
    apt-get clean
WORKDIR /home/dataman/n6/N6Portal/gui
RUN npm install && \
    npm run build
ADD docker/web/test_data/test-n6-portal.wsgi /home/dataman/n6/N6Portal/n6-portal.wsgi
ADD docker/web/test_data/test-portal-production.ini /home/dataman/n6/N6Portal/production.ini
ADD docker/web/test_data/test-n6-portal-api.conf /etc/apache2/sites-available/n6-portal-api.conf
RUN chown -R www-data:www-data /etc/apache2/sites-available/n6-portal-api.conf

# default website redirect to ssl connetions
ADD docker/web/test_data/test-000-default.conf /etc/apache2/sites-available/000-default.conf

# generate new app_secret_key
ADD docker/web/test_data/test-admin_panel.conf /etc/n6/admin_panel.conf
RUN app_secret_key=`python -c 'import os, base64; print(base64.b64encode(os.urandom(16)))'`;\
    sed -i "s/1dOvshmX+dU2Bl8XB0itYg==/$app_secret_key/g" /etc/n6/admin_panel.conf

# permissions
WORKDIR /home/dataman/n6
RUN mkdir -p /home/dataman/n6/.python-eggs; \
    chown -R www-data:www-data /home/dataman/n6/.python-eggs ;\
    chmod -R 744 /home/dataman/n6/.python-eggs ;\
    mkdir -p /var/log/n6; chmod 777 /var/log/n6

# apache config
RUN a2enmod wsgi && \
    a2enmod ssl && \
    a2enmod rewrite && \
    a2ensite 000-default && \
	a2ensite n6-api && \
	a2ensite n6-portal-api && \
	a2ensite n6-adminpanel

# rest docker commands
EXPOSE 80 443 4443 4444
ADD docker/web/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]

# helpers
# https://localhost:4444/
# https://localhost
# https://localhost/api/info
# https://localhost/login
# Username: login@example.com
# Organization: example.com
# Password: aaaa
# curl --cert /root/certs/cert.pem --key /root/certs/key.pem -k 'https://web:4443/search/events.json?time.min=2015-01-01T00:00:00'
# https://localhost:15671
# mongo --host mongo n6 -u admin -p password
# mongo --host mongo admin -u admin -p password
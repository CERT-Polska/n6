FROM debian:stretch-slim

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive
ARG username
ARG password

# APT settings
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

RUN set -ex; \
    curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash - ;\
    apt-get install -y nodejs && \
    apt-get clean

# commands with root privilege
RUN echo 'ServerName localhost' >> /etc/apache2/apache2.conf

# adding the standard user with required password
RUN groupadd -g 1000 $username && \
    useradd -rm -d /home/$username -s /bin/bash -g root -G dataman,sudo,www-data -u 1000 $username -p $password
RUN echo "$username	ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers

# cloning the repository
COPY --chown=$username . /home/$username/n6
WORKDIR /home/$username/n6

# installing n6 componenets
USER $username

# permission for n6 directory and virtualenv initialization
RUN sudo mkdir -p /etc/n6; \
    sudo chmod -R a+rw /etc/n6; \
    virtualenv n6-env

# speed up building images
RUN . n6-env/bin/activate && \
    pip install -r N6Lib/requirements; \
    pip install -r N6SDK/requirements

# n6 installation
RUN . n6-env/bin/activate && \
    ./do_setup.py N6Core N6Lib N6SDK N6RestApi N6Portal N6AdminPanel &&\
    yes | n6config

# apache2, n6adminpanel, n6portal configuration files
COPY docker/web/test_data/test-n6-api.conf /etc/apache2/sites-available/n6-api.conf
COPY docker/web/test_data/test-n6-adminpanel.conf /etc/apache2/sites-available/n6-adminpanel.conf
COPY docker/web/test_data/test-n6-portal-api.conf /etc/apache2/sites-available/n6-portal-api.conf
COPY docker/web/test_data/test-000-default.conf /etc/apache2/sites-available/000-default.conf
COPY docker/web/test_data/test-n6-api.wsgi /home/$username/n6/N6RestApi/n6-api.wsgi
COPY docker/web/test_data/test-production.ini /home/$username/n6/N6RestApi/production.ini
COPY docker/web/test_data/test-n6-portal.wsgi /home/$username/n6/N6Portal/n6-portal.wsgi
COPY docker/web/test_data/test-portal-production.ini /home/$username/n6/N6Portal/production.ini
COPY docker/web/test_data/test-config.json N6Portal/gui/src/config/config.json

# generate app_secret_key
COPY docker/web/test_data/test-admin_panel.conf /etc/n6/admin_panel.conf
RUN app_secret_key=`python -c 'import os, base64; print(base64.b64encode(os.urandom(16), b"-_").decode())'`;\
    sudo sed -i "s/1dOvshmX+dU2Bl8XB0itYg==/$app_secret_key/g" /etc/n6/admin_panel.conf

# npm install and build web application
WORKDIR /home/$username/n6/N6Portal/gui
RUN sudo npm i -g npm@latest && \
    sudo npm i -g --unsafe-perm node-sass && \
    npm install && \
    npm run build

# create distribution format packages
RUN mkdir -p /home/$username/n6/.python-eggs; \
    chown -R www-data:www-data /home/$username/n6/.python-eggs;\
    chmod -R 744 /home/$username/n6/.python-eggs

USER root

# n6 logs direcotory
RUN mkdir -p /var/log/n6; sudo chmod 777 /var/log/n6

# apache2 customization
RUN a2enmod wsgi && \
    a2enmod ssl && \
    a2enmod rewrite && \
    a2ensite 000-default && \
	a2ensite n6-api && \
	a2ensite n6-portal-api && \
	a2ensite n6-adminpanel

WORKDIR /home/$username/n6
COPY docker/web/entrypoint.sh /entrypoint.sh
RUN chmod a+x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]

EXPOSE 80 443 4443 4444
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD curl --insecure -f https://localhost/api/info || exit 1

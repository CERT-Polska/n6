FROM n6_base

ARG action=develop

COPY --chown=dataman:dataman . n6

# Install web components in Python 3 environment.
RUN . /home/dataman/env_py3k/bin/activate; \
    cd /home/dataman/n6/ && \
    ./do_setup.py -a $action N6Lib N6SDK N6RestApi N6Portal N6AdminPanel N6BrokerAuthApi;

# Install n6 Portal frontend
RUN sudo npm install --global yarn; \
    cd /home/dataman/n6/N6Portal/react_app \
    && yarn \
    && yarn build; \
    sudo npx -y playwright install --with-deps;

# Customization of configuration files.
RUN cp -f /home/dataman/n6/etc/n6/*.conf /home/dataman/.n6;

USER root

# Apache2 configuration
ADD etc/apache2/ /etc/apache2/
RUN a2enmod wsgi && \
    a2enmod ssl && \
    a2enmod rewrite && \
    a2ensite 000-default && \
    a2ensite n6-restapi && \
    a2ensite n6-portal && \
    a2ensite n6-adminpanel

EXPOSE 80 443 4443 4444
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD curl --insecure -f https://localhost/api/info || exit 1


# Some helpful links:
# Admin Panel: https://localhost:4444/
# N6 Portal GUI: https://localhost
# N6 Portal API: https://localhost/api
# N6 Portal API - user's authentication and authorization status info: https://localhost/api/info
# N6 Portal GUI - a sign-in view https://localhost/login

# Credentials for default user
# Username: login@example.com
# Password: entered when creating the user
# Organization: example.com

# How to make a request to N6 API
# $ curl --cert /home/dataman/certs/cert.pem --key /home/dataman/certs/key.pem -k 'https://web:4443/search/events.json?time.min=2015-01-01T00:00:00'

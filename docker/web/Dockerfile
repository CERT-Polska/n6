FROM n6_base

COPY --chown=dataman:dataman . n6

RUN . ~/env/bin/activate; \
    cd /home/dataman/n6/N6Portal/gui \
        && tar -zxf ~/node_modules.tar.gz \
        && cp -f /home/dataman/n6/etc/web/conf/gui-config.json src/config/config.json \
        && npm run build; \
    # install n6
    cd ~/n6 && \
    ./do_setup.py -a develop N6Lib N6SDK N6RestApi N6Portal N6AdminPanel N6BrokerAuthApi; \
    # configs
    cp -f ~/n6/etc/n6/*.conf /etc/n6/;

USER root

ADD etc/apache2/ /etc/apache2/
RUN a2enmod wsgi && \
    a2enmod ssl && \
    a2enmod rewrite && \
    a2ensite 000-default && \
    a2ensite n6-public-data && \
    a2ensite n6-api && \
    a2ensite n6-portal && \
    a2ensite n6-adminpanel

EXPOSE 80 443 4443 4444
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=5 \
CMD curl --insecure -f https://localhost/api/info || exit 1


# Some helpful links:
# Admin Panel: https://localhost:4444/
# N6 Portal: https://localhost
# N6 API: https://localhost/api/info
# https://localhost/login

# Credidentials for default user
# Username: login@example.com
# Organization: example.com

# How to make a request to N6 API
# $ curl --cert /home/dataman/certs/cert.pem --key /home/dataman/certs/key.pem -k 'https://web:4443/search/events.json?time.min=2015-01-01T00:00:00'

# How to get access to N6 Portal
# $ cd etc/ssl/generated_certs
# $ openssl pkcs12 -export -out ImportMetoWebBrowser.p12 -in cert.pem -inkey key.pem

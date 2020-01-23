FROM n6_base

COPY --chown=dataman:dataman . n6

RUN \
    . ~/env/bin/activate; \
    # install n6 modules
    cd ~/n6 && \
    ./do_setup.py -a develop N6Lib N6Core; \
    # configure supervisord
    cd ~ && mkdir -p supervisord/log supervisord/programs && \
    cd n6/etc/supervisord && \
    cp programs/*.conf ~/supervisord/programs/ && \
    python get_parsers_conf.py && \
    cp supervisord.conf ~/supervisord/; \
    # n6 configs
    yes | n6config; \
    cp -f ~/n6/etc/n6/*.conf /etc/n6/;

# Some helpful links:
# RabbitMQ management: https://localhost:15671

# Mysql
# $ mysql -h localhost -u root -ppassword

# Mongo
# $ mongo --host mongo n6 -u admin -p password
# $ mongo --host mongo admin -u admin -p password

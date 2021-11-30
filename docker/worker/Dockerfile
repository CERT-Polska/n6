FROM n6_base

ARG action=develop

COPY --chown=dataman:dataman . n6

# n6 installation in Python 2 environment
RUN \
    . ~/env/bin/activate; \
    # install n6 modules
    cd ~/n6 && \
    ./do_setup.py -a $action N6Lib-py2 N6CoreLib N6Core; \
    # configure supervisord
    mkdir -p ~/supervisord/log ~/supervisord/programs_py2k && \
    cd ~/n6/etc/supervisord && \
    ~/env/bin/python get_parsers_conf_py2k.py && \
    cp programs_py2k/*.conf ~/supervisord/programs_py2k/ && \
    cp supervisord_py2k.conf ~/supervisord/; \
    # n6 configs
    yes | n6config; \
    cp -f ~/n6/N6DataPipeline/n6datapipeline/data/conf/*.conf ~/.n6; \
    cp -f ~/n6/N6DataSources/n6datasources/data/conf/*.conf ~/.n6; \
    cp -f ~/n6/etc/n6/*.conf ~/.n6;

# n6 installation in Python 3 environment
RUN . ~/env_py3k/bin/activate; \
    # install n6 modules
    cd ~/n6; \
    ./do_setup.py -a $action N6Lib N6SDK N6DataPipeline N6DataSources; \
    # configure supervisord
    mkdir -p ~/supervisord/log ~/supervisord/programs && \
    cd ~/n6/etc/supervisord && \
    ~/env_py3k/bin/python get_parsers_conf.py && \
    cp programs/*.conf ~/supervisord/programs/ && \
    cp supervisord.conf ~/supervisord/;


# Some helpful links:
# RabbitMQ management: https://localhost:15671

# Mysql
# $ mysql -h localhost -u root -ppassword

# Mongo
# $ mongo --host mongo n6 -u admin -p password
# $ mongo --host mongo admin -u admin -p password
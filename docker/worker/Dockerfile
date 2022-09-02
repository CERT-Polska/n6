FROM n6_base

ARG action=develop

COPY --chown=dataman:dataman . n6

# n6 installation in Python 2 environment
RUN . /home/dataman/env/bin/activate; \
    cd /home/dataman/n6 && \
    ./do_setup.py -a $action N6Lib-py2 N6CoreLib N6Core;

# n6 installation in Python 3 environment
RUN . /home/dataman/env_py3k/bin/activate; \
    cd /home/dataman/n6; \
    ./do_setup.py -a $action N6Lib N6SDK N6DataPipeline N6DataSources;

# Customization of configuration files.
RUN . /home/dataman/env/bin/activate; \
    mkdir -p /home/dataman/supervisord/log \
             /home/dataman/supervisord/programs_py2k \
             /home/dataman/supervisord/programs && \
    cd /home/dataman/n6/etc/supervisord && \
    /home/dataman/env/bin/python get_parsers_conf_py2k.py && \
    cp programs_py2k/*.conf /home/dataman/supervisord/programs_py2k/ && \
    cp supervisord_py2k.conf /home/dataman/supervisord/; \
    /home/dataman/env_py3k/bin/python get_parsers_conf.py && \
    cp programs/*.conf /home/dataman/supervisord/programs/ && \
    cp supervisord.conf /home/dataman/supervisord/ && \
    # n6 configs
    yes | n6config; \
    cp -f /home/dataman/n6/N6DataPipeline/n6datapipeline/data/conf/*.conf /home/dataman/.n6; \
    cp -f /home/dataman/n6/N6DataSources/n6datasources/data/conf/*.conf /home/dataman/.n6; \
    cp -f /home/dataman/n6/etc/n6/*.conf /home/dataman/.n6;

# Some helpful links:
# RabbitMQ management: https://localhost:15671

# Mysql
# $ mysql -h localhost -u root -ppassword

# Mongo
# $ mongo --host mongo n6 -u admin -p password
# $ mongo --host mongo admin -u admin -p password
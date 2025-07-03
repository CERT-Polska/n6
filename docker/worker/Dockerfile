FROM n6_base

ARG action=develop

COPY --chown=dataman:dataman . n6

# TODO: get rid of, no longer necessary, Python-2-related stuff...

# Optional installation of old Python-2 stuff. Now, **only if** you
# provide that stuff manually (for some experimentation, if you are
# interested in such ancient stuff). Normally, **you don't need it.**
# [TODO: remove]
RUN ( . /home/dataman/env/bin/activate && \
      cd /home/dataman/n6/misc-nonpub/old-code-py2 && \
      ./do_setup.py -a $action N6Lib-py2 N6CoreLib N6Core ; true )

# Actual installation of *n6* (in Python 3 environment)
RUN . /home/dataman/env_py3k/bin/activate && \
    cd /home/dataman/n6 && \
    # XXX: `-p 'freezegun==0.3.4'` is temporarily needed for certain custom stuff... (TODO later: remove it from here)
    ./do_setup.py -b -x tests -p 'freezegun==0.3.4' -a $action N6Lib N6SDK N6DataPipeline N6DataSources  # `-b` <- Install also "bonus" (optional custom) stuff if available...

# Customization of configuration files
RUN mkdir -p /home/dataman/supervisord/log \
             /home/dataman/supervisord/programs_py2k \
             /home/dataman/supervisord/programs && \
    cd /home/dataman/n6/etc/supervisord && \
    # (the following 5 lines are related to old Python-2 stuff) [TODO: remove]
    ( . /home/dataman/env/bin/activate && \
      /home/dataman/env/bin/python get_parsers_conf_py2k.py && \
      cp programs_py2k/*.conf /home/dataman/supervisord/programs_py2k/ && \
      cp supervisord_py2k.conf /home/dataman/supervisord/ && \
      yes | n6config ; true ) && \
    /home/dataman/env_py3k/bin/python get_parsers_conf.py && \
    cp programs/*.conf /home/dataman/supervisord/programs/ && \
    cp supervisord.conf /home/dataman/supervisord/ && \
    cp -f /home/dataman/n6/etc/n6/*.conf /home/dataman/.n6 && \
    ( cp -f /home/dataman/n6/etc-*/n6/*.conf /home/dataman/.n6 ; true )  # <- Configs for "bonus" (optional custom) stuff if available...

# Some helpful links:
# RabbitMQ management: https://localhost:15671

# Mysql
# $ mysql -h localhost -u root -ppassword

# Mongo
# $ mongo --host mongo n6 -u admin -p password
# $ mongo --host mongo admin -u admin -p password

FROM mariadb:10.3

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive
# additional apt settings
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99AcquireRetries

# mysql config
ADD docker/mysql/test_data/test-mariadb.cnf /etc/mysql/conf.d/my_own.cnf

# database schema
ADD docker/mysql/test_data/test-create_tables.sql /docker-entrypoint-initdb.d/1-create_tables.sql
# Commented out due to long startup process
#ADD etc/sql/create_indexes.sql /docker-entrypoint-initdb.d/2-create_indexes.sql
ADD docker/mysql/test_data/test-auth_db.sql /docker-entrypoint-initdb.d/3-create_auth_db.sql
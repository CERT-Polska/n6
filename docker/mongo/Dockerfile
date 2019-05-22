FROM mongo:4

# interactive mode
ENV TERM xterm
ENV DEBIAN_FRONTEND noninteractive

# create new database for n6 usage
ADD docker/mongo/test-data/mongodb-setup.js /docker-entrypoint-initdb.d

EXPOSE 27017

# mongo admin --host mongo --port 27017 -u admin -password password
# mongo n6 --host mongo --port 27017 -u admin -password password
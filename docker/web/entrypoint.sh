#!/bin/sh

# overwrite n6 config files
cp -f docker/work/test_data/test-logging.conf /etc/n6/logging.conf
cp -f docker/work/test_data/test-00_global.conf /etc/n6/00_global.conf
cp -f docker/work/test_data/test-02_archiveraw.conf /etc/n6/02_archiveraw.conf
cp -f docker/work/test_data/test-05_enrich.conf /etc/n6/05_enrich.conf
cp -f docker/work/test_data/test-09_auth_db.conf /etc/n6/09_auth_db.conf
cp -f docker/work/test_data/test-21_recorder.conf /etc/n6/21_recorder.conf

service rsyslog start

exec "$@"
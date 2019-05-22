#!/bin/sh

# overwrite data config n6 files
mkdir -p /etc/n6/
cp -f docker/work/test_data/test-logging.conf /etc/n6/logging.conf
cp -f docker/work/test_data/test-00_global.conf /etc/n6/00_global.conf
cp -f docker/work/test_data/test-02_archiveraw.conf /etc/n6/02_archiveraw.conf
cp -f docker/work/test_data/test-05_enrich.conf /etc/n6/05_enrich.conf
cp -f docker/work/test_data/test-09_auth_db.conf /etc/n6/09_auth_db.conf
cp -f docker/work/test_data/test-21_recorder.conf /etc/n6/21_recorder.conf
chmod -R o+r /etc/n6/

service rsyslog start

exec "$@"
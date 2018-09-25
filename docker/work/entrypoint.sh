#!/bin/sh

set -ex

# default config n6 files
rm -rf /etc/n6/*
yes | n6config

# overwrite data config n6 files
cp -f docker/work/test_data/test-logging.conf /etc/n6/logging.conf
cp -f docker/work/test_data/test-00_global.conf /etc/n6/00_global.conf
cp -f docker/work/test_data/test-02_archiveraw.conf /etc/n6/02_archiveraw.conf
cp -f docker/work/test_data/test-05_enrich.conf /etc/n6/05_enrich.conf
cp -f docker/work/test_data/test-07_aggregator.conf /etc/n6/07_aggregator.conf
cp -f docker/work/test_data/test-07_comparator.conf /etc/n6/07_comparator.conf
cp -f docker/work/test_data/test-09_auth_db.conf /etc/n6/09_auth_db.conf
cp -f docker/work/test_data/test-21_recorder.conf /etc/n6/21_recorder.conf
cp -f docker/work/test_data/test-23_filter.conf /etc/n6/23_filter.conf
cp -f docker/work/test_data/test-70_abuse_ch.conf /etc/n6/70_abuse_ch.conf
cp -f docker/work/test_data/test-70_misp.conf /etc/n6/70_misp.conf
cp -f docker/work/test_data/test-70_zone_h.conf /etc/n6/70_zone_h.conf
wget -qO - http://geolite.maxmind.com/download/geoip/database/asnum/GeoIPASNum.dat.gz | gunzip -c > /usr/share/GeoIP/GeoIPASNum.dat

# temp files
mkdir -p /tmp/data
chmod 777 /tmp/data

# pickle configuration module
mkdir -p /var/cache/n6
chmod 777 /var/cache/n6
/wait-for-services.sh -- echo "All docker containers UP!"

service cron start

exec "$@"
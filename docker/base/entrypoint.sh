#!/bin/sh
sudo service rsyslog start
. /home/dataman/env/bin/activate
exec "$@"

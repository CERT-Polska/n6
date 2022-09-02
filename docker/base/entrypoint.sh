#!/bin/sh
sudo service rsyslog start >/dev/null 2>&1
. /home/dataman/env_py3k/bin/activate
exec "$@"

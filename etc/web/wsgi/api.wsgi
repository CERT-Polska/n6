#!/usr/bin/python
from pyramid.paster import get_app, setup_logging
ini_path = '/home/dataman/n6/etc/web/conf/api.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')

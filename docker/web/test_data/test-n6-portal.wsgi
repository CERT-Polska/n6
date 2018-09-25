from pyramid.paster import get_app, setup_logging
ini_path = '/home/dataman/n6/N6Portal/production.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')
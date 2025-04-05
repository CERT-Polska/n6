#!/usr/bin/env python

# Let's apply n6 specific monkey-patching as early as possible.
import n6lib  # noqa

from pyramid.paster import get_app, setup_logging
ini_path = '/home/dataman/apa_config/brokerauthapi.ini'
setup_logging(ini_path)
application = get_app(ini_path, 'main')

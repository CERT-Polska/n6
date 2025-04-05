#!/usr/bin/env python

# Let's apply n6 specific monkey-patching as early as possible.
import n6lib  # noqa

from n6adminpanel.app import get_app
application = get_app()

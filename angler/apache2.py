#!/usr/bin/env python

from angler.common import *

logging = getLogger('apache2')

sites_available_dir = Folder('/etc/apache2/sites-available')
sites_enabled_dir = Folder('/etc/apache2/sites-enabled')

class Server(Definition):
	def __init__(self):
		Package('apache2') > self
		Service('apache2', state='running')
		Definition.__init__(self)
		

#!/usr/bin/env python

from angler.common import *

from collections import OrderedDict as od

logging = getLogger('apache2')

sites_available_dir = Folder('/etc/apache2/sites-available')
sites_enabled_dir = Folder('/etc/apache2/sites-enabled')

class Server(Definition):
	def __init__(self):
		Package('apache2') > self
		Service('apache2', state='running')
		Definition.__init__(self)

class Apache2File(Path):
	def __init__(self, path):
		Path.__init__(self, path, state='file')

	@param
	def content(self):
		def parse_block(I, end=None):
			for line in I:
				line = line.partition('#')[0].strip()
				if not line:
					continue
				if line.startswith('<'):
					if end and line == '</%s>' % end:
						return
					else:
						cmd,args = line[1:-1].split(None, 1)
						yield (cmd,args), od(parse_block(I, cmd))
				else:
					cmd,args = line.split(None, 1)
					yield cmd, args
		return od(parse_block(iter(open(self.path,'rb'))))
	@content.validator
	def content(self, new):
		if isinstance(new, dict):
			return new
		elif isinstance(new, SEQUENCE_TYPES):
			return od(new)
		raise InvalidParam

	def runners(self):
		print self.content()
		raise Exception
		yield
		
class Conf(Definition):
	def __init__(self):
		Definition.__init__(self)
		self.ports_conf = Apache2File('/etc/apache2/ports.conf')
		print self.ports_conf.content()

	@param
	def http_port(self):
		return int(self.ports_conf['Listen'])
	@http_port.validator
	def http_port(self, new):
		if isinstance(new, int) and 0 <= new <= 65535:
			return new
		raise InvalidParam

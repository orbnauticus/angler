#!/usr/bin/env python

from ..common import *
from angler import *
#from angler.system import *

Hosts = File('/etc/hosts')#, owner=User('root'), group=User('root'))

class Aliases(Definition):
	@param.read_only
	def aliases(self):
		result = {}
		for line in Hosts.content().split('\n'):
			line = line.partition('#')[0].strip().split()
			if line:
				target = line.pop(0)
				for name in line:
					result[name] = target
		return result

	def append(self, name, target):
		Hosts.content = Hosts.content() + ('%s\t%s\n' % (target, name))
		self.aliases()[name] = target

Aliases = Aliases()

class Alias(Definition):
	def __init__(self, name):
		Definition.__init__(self, name)
		Aliases > self > Hosts

	present = param.boolean('present', True)

	@param('127.0.0.1')
	def target(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid target: %r" % new

	def append_to_hosts(self):
		Aliases.append(self.name, self.target())

	def remove_from_hosts(self):
		raise NotImplementedError

	def runners(self):
		if self.present():
			if self.name in Aliases.aliases():
				if Aliases.aliases()[self.name] != self.target():
					yield self.remove_from_hosts
			if self.name not in Aliases.aliases():
				yield self.append_to_hosts
		else:
			raise NotImplementedError

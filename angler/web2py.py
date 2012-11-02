#!/usr/bin/env python

from .common import *
from .package import *
#from .system import *

from angler import apache2

class web2py(Definition):
	def __init__(self):
		Package('apache2') > self

web2py = web2py()

class Server(Definition):
	def __init__(self):
		Definition.__init__(self)
		git_repo = 'git://github.com/mdipierro/web2py.git'
		apache2.Mod('wsgi')
		apache2.Mod('rewrite')
		apache2.Mod('ssl')
		Package('git-core')
		Folder('/var/cache/puppet/web2py')
		

class Site(Definition):
	def __init__(self, name):
		Definition.__init__(self, name)


	@param()
	def app_repo(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid app_repo: %r" % new

	@param()
	def domain(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid domain: %r" % new

	@param()
	def ssl_cert(self, new):
		if isinstance(new, basestring) or new is None:
			return new
		raise ValueError, "Invalid ssl_cert: %r" % new

	@param()
	def group(self, new):
		if isinstance(new, (Group, fact)):
			return new
		elif isinstance(new, basestring):
			return Group(new)
		elif isinstance(new, int):
			return Group.fromgid(new)
		raise ValueError, "Invalid group: %r" % new

	@param()
	def user(self, new):
		if isinstance(new, (User, fact)):
			return new
		elif isinstance(new, basestring):
			return User(new)
		elif isinstance(new, int):
			return User.fromuid(new)
		raise ValueError, "Invalid user: %r" % new

	@param()
	def version_regex(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid version_regex: %r" % new

	enabled = param.boolean('enabled', True)

	@param()
	def post_merge(self, new):
		if isinstance(new, basestring) or new is None:
			return new
		raise ValueError, "Invalid post_merge: %r" % new

	@param()
	def app_branch(self, new):
		if isinstance(new, basestring) or new is None:
			return new
		raise ValueError, "Invalid app_branch: %r" % new

	@param()
	def site_aliases(self, new):
		if isinstance(new, SEQUENCE_TYPES):
			return new
		raise ValueError, "Invalid site_aliases: %r" % new

class app(Definition):
	__name__ = 'web2py.app'
	def __init__(self, root):
		Definition.__init__(self, root)
		web2py() > self
		root.child('__init__.py', state='file') > self
		folders = ('cache', 'controllers', 'cron', 'databases', 'errors',
		 'languages', 'models', 'modules', 'private', 'sessions',
		 'uploads', 'views') 
		for f in folders:
			root.child(f, state='folder') > self
		root.child('modules').child('__init__.py', state='file', content='') > self
		static = root.child('static', state='folder')
		for f in ('images', 'js', 'css'):
			static.child(f, state='folder') > self

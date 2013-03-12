#!/usr/bin/env python

import _abcoll
import collections
import grp
import inspect
import hashlib
import logging
import os
import platform
import pwd
import re
import shutil
import socket
import spwd
from subprocess import Popen, PIPE
import sys
import topsort

logger = logging.getLogger()

class collection(dict): __getattr__,__setattr__,__delattr__ = dict.get,dict.__setitem__,dict.__delitem__

def md5sum(content):
	return hashlib.md5(content).hexdigest()

class ReturnCode(Exception):
	def __init__(self, cmd, expected, got, (stdout, stderr)):
		Exception.__init__(self, "Expected %i, got %i from command %r" % (expected, got, ' '.join(map(str,cmd))))
		self.cmd = cmd
		self.expected = expected
		self.got = got
		self.stdout = stdout
		self.stderr = stderr

def RUN(*cmd, **kwargs):
	logger.debug('shell exec %s', ' '.join(map(str,cmd)))
	kwargs.setdefault('stdout', PIPE)
	kwargs.setdefault('stderr', PIPE)
	code = int(kwargs.pop('expect', 0))
	proc = Popen(map(str,cmd), **kwargs)
	result = proc.communicate(kwargs.get('stdin',''))
	if proc.returncode != code:
		raise ReturnCode(cmd, code, proc.returncode, result)
	return result

def GREP(pattern, source):
	return [line for line in source.split('\n') if re.match(pattern, line)]

SEQUENCE_TYPES = (list, tuple, set, frozenset)

class Manifest(collections.MutableMapping):
	def __init__(self):
		self.defs = collections.defaultdict(dict)
		self.sorter = topsort.Topsort()
		self.skipped = 0
		self.runned = 0
		self.errors = 0

	def __getitem__(self, key):
		return self.defs[key]

	def __setitem__(self, key, value):
		self.defs[key] = value

	def __delitem__(self, key):
		del self.defs[key]

	def __len__(self):
		return len(self.defs)

	def __iter__(self):
		return iter(self.defs)

	def add(self, obj, dep):
		self.sorter.add(obj, dep)
		for i in self.sorter:
			pass

	def discard(self, obj, dep):
		self.sorter.discard(obj, dep)

	def clear(self):
		self.__init__()

	def __enter__(self):
		self.clear()

	def __exit__(self, obj, exc, tb):
		if obj is None:
			self.run()

	@staticmethod
	def format_items(items):
		return ' '.join('%s=%s' % (k,`v` if len(`v`) < 21 else \
		(`v`[:9]+'...'+`v`[-9:] if isinstance(v, basestring) else \
		'%s(#items=%i)' % (v.__class__.__name__, len(v)) if isinstance(v, SEQUENCE_TYPES) else \
		`v`)) for k,v in sorted(items))

	@property
	def def_count(self):
		return self.skipped + self.runned + self.errors

	def run(self, dryrun=False):
		self.skipped = self.runned = self.errors = 0
		logger = logging.getLogger(' ')
		try:
			for node in list(self.sorter):
				if node is None:
					logger.info('Finished processing %i definitions (%i run, %i skipped, %i errors)', self.def_count, self.runned, self.skipped, self.errors)
				elif not isinstance(node, fact):
					try:
						runners = node.runners()
					except AttributeError:
						continue
					try:
						counts = False
						for runner in runners:
							if not counts:
								logger.info('Running %s %s', node, self.format_items(node.items()))
							counts = True
							self.runned += 1
							dryrun or runner()
						if not counts:
							self.skipped += 1
							logger.debug('Skipping %s %s', node, self.format_items(node.items()))
					except (KeyboardInterrupt,SystemError):
						raise
					except Exception, e:
						logger.exception('Encountered error processing %s %s', node, self.format_items(node.items()))
						self.errors += 1
		except KeyboardInterrupt:
			sys.exit(1)

manifest = Manifest()

class Proxy(collections.MutableMapping):
	def __init__(self, parent):
		self.__parent = parent

	def __getitem__(self, key):
		return self.__parent[key]

	def __setitem__(self, key, value):
		self.__parent[key] = value

	def __delitem__(self, key):
		del self.__parent[key]

	def __len__(self):
		return len(self.__parent)

	def __iter__(self):
		return iter(self.__parent)

class ProxyVal(object):
	def __init__(self, get_parent, name=None):
		self.parent = get_parent
		self.name = name or get_parent.func_name

	def __get__(self, inst, owner):
		if inst is None:
			return self
		return self.parent(inst)[self.name]

	def __set__(self, inst, value):
		self.parent(inst)[self.name] = value

	def __delete__(self, inst):
		del self.parent(inst)[self.name]

class InvalidParam(Exception): pass

class param(ProxyVal):
	def __init__(self, default=None):
		if inspect.isfunction(default):
			self.default = default
			self.name = default.func_name
		else:
			self.default = lambda s:default

	def __call__(self, validate):
		ProxyVal.__init__(self, validate)
		self.name = validate.func_name
		self.validate = validate
		return self

	def fetch(self, func):
		self.default = func
		return self

	def validator(self, func):
		self.validate = func
		return self

	def __get__(self, inst, owner):
		if inst is None:
			return self
		return fact(inst, self)

	def __set__(self, inst, value):
		try:
			inst.unrequires(self.__get__(inst, None))
		except KeyError:
			pass
		try:
			result = self.validate(inst, value)
		except InvalidParam, e:
			
			raise e
		if isinstance(result, (fact, Definition)):
			inst.requires(result)
		inst.manifest[inst.args][self.name] = result
		return result

	@classmethod
	def enum(cls, *values, **kwargs):
		default = kwargs.pop('default', None)
		if default not in values:
			values = values + (default,)
		def decorator(validate):
			def validator(self, new):
				new = validate(self, new)
				if new not in values:
					raise ValueError, "Invalid value %s must be one of %s" % (self.__class__.__name__, values)
				return new
			validator.func_name = validate.func_name
			return cls(default)(validator)
		return decorator

	@classmethod
	def read_only(cls, func):
		def validate(self, new):
			raise ValueError, "Parameter %s is read-only" % func.func_name
		validate.func_name = func.func_name
		return cls(func)(validate)

	@classmethod
	def boolean(cls, name, default=True):
		valid = lambda s,n:bool(n)
		valid.func_name = name
		return cls(default)(valid)

class ManifestMetaClass(_abcoll.ABCMeta):
	def __new__(cls, name, parents, attr):
		if '__name__' in attr:
			name = attr['__name__']
		try:
			arg_names = inspect.getargspec(attr['__init__']).args[1:]
		except KeyError:
			arg_names = attr.pop('args', ())
		def_props = dict((k,v) for k,v in attr.items() if isinstance(v, param))
		init = attr.get('__init__', lambda *a,**k:None)
		if '__init__' not in attr:
			def __init__(self, *args, **kwargs):
				if len(args) > len(arg_names):
					raise TypeError, "Expected %i arguments, got %i" % (len(arg_names), len(args))
				for key in kwargs:
					def_props[key].__set__(self, kwargs[key])
				super(self.__class__, self).__init__(*args)
			attr['__init__'] = __init__
		for i,arg in enumerate(arg_names):
			attr.setdefault(arg, property(lambda self:self.args[i+1]))
		if inspect.getargspec(attr['__init__']).keywords is None:
			init = attr['__init__']
			def __init__(self, *args, **kwargs):
				init(self, *args)
				self.update(**kwargs)
			attr['__init__'] = __init__
		return super(ManifestMetaClass, cls).__new__(cls, name, parents, attr)

class Definition(Proxy):
	__metaclass__ = ManifestMetaClass
	manifest = manifest
	def __init__(self, *args, **kwargs):
		self.args = (self.__class__.__name__,) + args
		Proxy.__init__(self, self.manifest[self.args])
		self.manifest.add(None, self)

	def update(self, **kwargs):
		for key in kwargs:
			setattr(self, key, kwargs[key])

	def __hash__(self):
		return hash(self.args)

	def __repr__(self):
		return '%s(%s)' % (self.args[0], ', '.join(map(repr,self.args[1:])))

	def requires(self, other):
		self = getattr(self, 'dep_standin', self)
		other = getattr(other, 'dep_standin', other)
		self.manifest.add(self, other)

	def unrequires(self, other):
		self = getattr(self, 'dep_standin', self)
		other = getattr(other, 'dep_standin', other)
		self.manifest.discard(self, other)

	def __lt__(self, other):
		if isinstance(other, SEQUENCE_TYPES):
			for o in other:
				self.requires(o)
		else:
			self.requires(other)
		return True

	def __gt__(self, other):
		if isinstance(other, SEQUENCE_TYPES):
			for o in other:
				o.requires(self)
		else:
			other.requires(self)
		return True

class fact(object):
	def __init__(self, inst, param):
		self.inst = inst
		self.param = param

	def __call__(self):
		proxy = self.inst.manifest[self.inst.args]
		try:
			value = proxy[self.param.name]
		except KeyError:
			value = self.param.default(self.inst)
		return value() if isinstance(value, fact) else value

	def __getattr__(self, name):
		return getattr(self(), name)

	def __repr__(self):
		return `self()`

def partialclass(*args, **kwargs):
	def newfunc(cls, *fargs, **fkwargs):
		newkwargs = kwargs.copy()
		newkwargs.update(fkwargs)
		return cls(*(args + fargs), **newkwargs)
	return classmethod(newfunc)

logger = logging.getLogger('system')

class mode(int):
	def __new__(cls, val):
		return int.__new__(cls, val & 0777)
	
	def __repr__(self):
		return '%04o' % int(self)

	def x_folder(self):
		return mode(self | ((self & 0444) >> 2))

class Path(Definition):
	def __init__(self, path):
		Definition.__init__(self, path)
		try:
			self.requires(self.parent)
		except OSError:
			pass

	def child(self, path, **kwargs):
		kwargs.setdefault('state', 'folder')
		return Path(os.path.join(self.path, path), **kwargs)

	@property
	def parent(self):
		p, _ = os.path.split(self.path)
		if len(p) > 1:
			return Path(p, state='folder')
		else:
			raise OSError, "Root has no parent"

	@param.enum('folder', 'file', 'absent', 'link')
	def state(self, new):
		return new.lower()
	@state.fetch
	def state(self):
		if os.path.exists(self.path):
			if os.path.isdir(self.path):
				return 'folder'
			elif os.path.islink(self.path):
				return 'link'
			elif os.path.isfile(self.path):
				return 'file'
		else:
			return 'absent'

	@param
	def owner(self):
		return User.fromuid(os.stat(self.path).st_uid)
	@owner.validator
	def owner(self, new):
		if isinstance(new, (User, fact)):
			return new
		elif isinstance(new, basestring):
			return User(new)
		elif isinstance(new, int):
			return User.fromuid(new)
		raise ValueError, "Invalid user: %r" % new

	@param
	def group(self):
		return Group.fromgid(os.stat(self.path).st_gid)
	@group.validator
	def group(self, new):
		if isinstance(new, (Group, fact)):
			return new
		elif isinstance(new, basestring):
			return Group(new)
		elif isinstance(new, int):
			return Group.fromgid(new)
		raise ValueError, "Invalid group: %r" % new

	@param
	def mode(self):
		if os.path.exists(self.path):
			return mode(os.stat(self.path).st_mode)
		else:
			return mode(0644)
	@mode.validator
	def mode(self, new):
		if isinstance(new, int):
			return mode(new)
		raise ValueError, "Invalid mode: %r" % new

	@param
	def content(self):
		if os.path.exists(self.path):
			return open(self.path, 'rb').read()
		else:
			return None
	@content.validator
	def content(self, new):
		if isinstance(new, (basestring, fact)) or new is None:
			return new
		raise ValueError, "Invalid file content: %r" % new

	def create_folder(self):
		getLogger('path').debug('os.mkdir(%r)', self.path)
		os.mkdir(self.path)

	def create_file(self):
		getLogger('path').debug("open(%r, 'wb').write(~%s~)", self.path, md5sum(self.content()))
		open(self.path, 'wb').write(self.content())

	def create_link(self):
		getLogger('path').debug("os.symlink(%r, %r)", self.path, self.content())
		os.symlink(self.content(), self.path)

	def remove(self):
		if os.path.isdir(self.path):
			getLogger('path').debug('shutil.rmtree(%r)', self.path)
			shutil.rmtree(self.path)
		else:
			getLogger('path').debug('os.unlink(%r)', self.path)
			os.unlink(self.path)

	def chown(self):
		s = os.stat(self.path)
		uid, gid = -1, -1
		if s.st_uid != self.owner().uid():
			uid = self.owner().uid()
		if s.st_gid != self.group().gid():
			gid = self.group().gid()
		if (uid, gid) != (-1, -1):
			getLogger('path').debug("os.lchown(%r, %r, %r)", self.path, uid, gid)
			os.lchown(self.path, uid, gid)

	def chmod(self):
		m = self.mode()
		if self.state() == 'folder':
			m = m.x_folder()
		getLogger('path').debug("os.lchmod(%r, %o)", self.path, m)

	def runners(self):
		state = self.state()
		exists = os.path.exists(self.path)
		if state == 'absent':
			if exists:
				yield self.remove
		else:
			m = self.mode()
			if state == 'folder':
				m = m.x_folder()
				if not exists:
					yield self.create_folder
			elif state == 'file':
				if self.content() is None:
					open(self.path)
				elif not exists or open(self.path,'rb').read() != self.content():
					yield self.create_file
			elif state == 'link':
				if not exists:
					yield self.create_link
			s = os.stat(self.path)
			if s.st_uid != self.owner().uid() or s.st_gid != self.group.gid():
				yield self.chown
			if m != mode(s.st_mode):
				yield self.chmod

	Folder = partialclass(state='folder')
	File = partialclass(state='file')
	Link = partialclass(state='link')

File   = Path.File
Folder = Path.Folder
Link   = Path.Link

def getpwd(name):
	try:
		return pwd.getpwnam(name)
	except KeyError:
		p = type('struct_pwd', (object,), {})()
		p.pw_uid = None
		p.pw_gid = None
		p.pw_name = name
		p.pw_gecos = None
		p.pw_dir = None
		p.pw_shell = None
		return p

class User(Definition):
	def __init__(self, name):
		Definition.__init__(self, name)
		self < Group(name)

	present = param.boolean('present', True)

	@param
	def password(self):
		return getpwd(self.name).pw_passwd
	@password.validator
	def password(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid password: %r" % new

	@param
	def uid(self):
		return getpwd(self.name).pw_uid
	@uid.validator
	def uid(self, new):
		if not isinstance(new, (fact, int)):
			raise ValueError, "Invalid uid: %r" % new
		return new

	@param
	def group(self):
		return Group.fromgid(getpwd(self.name).pw_gid)
	@group.validator
	def group(self, new):
		if isinstance(new, (Group, fact)):
			return new
		elif isinstance(new, basestring):
			return Group(new)
		elif isinstance(new, int):
			return Group.fromgid(new)
		raise ValueError, "Invalid Group: %r" % new

	@param
	def comment(self):
		return getpwd(self.name).pw_gecos
	@comment.validator
	def comment(self, new):
		if not isinstance(new, basestring):
			raise ValueError, "Invalid comment: %r" % new
		return new

	@param
	def homedir(self):
		try:
			return Folder(pwd.getpwnam(self.name).pw_dir)
		except KeyError:
			return Folder('/home/%s' % self.name, owner=self)
	@homedir.validator
	def homedir(self, new):
		if isinstance(new, Path):
			return new
		elif isinstance(new, basestring):
			return Folder(new)
		raise ValueError, "Invalid homedir: %r" % new

	@param
	def shell(self):
		return getpwd(self.name).pw_shell or '/bin/sh'
	@shell.validator
	def shell(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid shell: %r" % new

	@param
	def groups(self):
		try:
			return set(Group(g.gr_name) for g in grp.getgrall() if self.name in g.gr_mem)
		except KeyError:
			return set()
	@groups.validator
	def groups(self, new):
		if isinstance(new, (list,tuple,set)):
			return set(new)
		raise ValueError, "Invalid groups: %r" % new

	@classmethod
	def fromuid(cls, uid):
		return cls(pwd.getpwuid(uid).pw_name)

	def create(self):
		RUN('useradd', '-N', '-M', self.name)

	def set_homedir(self):
		RUN('usermod', '-d', self.homedir().path, self.name)

	def set_uid(self):
		RUN('usermod', '-u', self.uid(), self.name)

	def set_group(self):
		RUN('usermod', '-g', self.group().gid(), self.name)

	def set_comment(self):
		RUN('usermod', '--comment', self.comment(), self.name)

	def set_shell(self):
		RUN('usermod', '--shell', self.shell(), self.name)

	def set_password(self):
		raise NotImplementedError

	def set_groups(self):
		RUN('usermod', '-G', ','.join(g.name for g in self.groups()), self.name)

	def delete(self):
		RUN('userdel', self.name)

	def runners(self):
		try:
			entry = pwd.getpwnam(self.name)
		except KeyError:
			if self.present():
				yield self.create
				entry = pwd.getpwnam(self.name)
		if not self.present():
			yield self.delete
		else:
			if entry.pw_dir != self.homedir().path:
				yield self.set_homedir
			if entry.pw_uid != self.uid():
				yield self.set_uid
			if self.group() and entry.pw_gid != self.group().gid():
				yield self.set_group
			if entry.pw_gecos != self.comment():
				yield self.set_comment
			if entry.pw_shell != self.shell():
				yield self.shell
			if self.groups() != set(Group(g.gr_name) for g in grp.getgrall() if self.name in g.gr_mem):
				yield self.set_groups

def AdminUser(*args, **kwargs):
	return User(*args, **kwargs)

def SysUser(*args, **kwargs):
	return User(*args, **kwargs)

def getgr(name):
	try:
		return grp.getgrnam(name)
	except KeyError:
		p = type('struct_grp', (object,), {})()
		p.gr_gid = None
		p.gr_name = name
		p.gr_mem = []
		p.gr_passwd = None
		return p

class Group(Definition):
	args = ['name']

	present = param.boolean('present', True)
	
	@param
	def gid(self):
		return getgr(self.name).gr_gid
	@gid.validator
	def gid(self, new):
		if isinstance(new, int):
			return new
		raise ValueError, "Invalid gid: %r" % new

	@classmethod
	def fromgid(cls, gid):
		if gid is None:
			return None
		return cls(grp.getgrgid(gid).gr_name)

	def add(self, user):
		user = User(user) if isinstance(user, basestring) else user
		self > user
		groups = user.groups()
		groups.add(self)
		user.groups = groups

	def create_group(self):
		cmd = ['groupadd']
		if self.gid():
			cmd.extend(['-g', self.gid()])
		cmd.append(self.name)
		RUN(*cmd)

	def delete_group(self):
		logger.debug(groupdel)
		RUN('groupdel', self.name)

	def set_gid(self):
		raise NotImplementedError

	def runners(self):
		try:
			entry = grp.getgrnam(self.name)
		except KeyError:
			if self.present():
				yield self.create_group
				entry = grp.getgrnam(self.name)
		if not self.present():
			yield self.delete_group
		else:
			if self.gid() is not None and entry.gr_gid != self.gid():
				yield self.set_gid

class Exec(Definition):
	args = ['name']

	@param
	def command(self):
		return self.name
	@command.validator
	def command(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid command: %r" % new

class Service(Definition):
	args = ['name']

	@param.enum('running', 'stopped')
	def state(self, new):
		return new.lower()
	@state.fetch
	def state(self):
		open('/var/run/%s.pid').read()

class System(Definition):
	@param.read_only
	def platform(self):
		return 'linux'

	@param.read_only
	def distribution(self):
		return 'ubuntu'

	@param.read_only
	def domain(self):
		return socket.getfqdn()

	@param.read_only
	def hostname(self):
		return socket.gethostname()

System = System()

class Host(object):
	def __init__(self, match=''):
		self.match = match
		
	def __nonzero__(self):
		return self.match == '' or re.match(self.match, System.hostname()) is not None

class Cache(Definition):
	#TODO: Cache is a remote file which is fetched whenever it's needed and kept
	#around as long as cached files don't exceed a configurable size quota.
	pass

from logging import getLogger, debug, info, warning, error, critical

from package import Package

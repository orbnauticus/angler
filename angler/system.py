#!/usr/bin/env python

from .common import *

import grp
import logging
import os
import platform
import pwd
import re
import shutil
import socket
import spwd

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

	@enum_param('folder', 'file', 'absent', 'link')
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

	@param()
	def owner(self, new):
		if isinstance(new, (User, fact)):
			return new
		elif isinstance(new, basestring):
			return User(new)
		elif isinstance(new, int):
			return User.fromuid(new)
		raise ValueError, "Invalid user: %r" % new
	@owner.fetch
	def owner(self):
		return User.fromuid(os.stat(self.path).st_uid)

	@param()
	def group(self, new):
		if isinstance(new, (Group, fact)):
			return new
		elif isinstance(new, basestring):
			return Group(new)
		elif isinstance(new, int):
			return Group.fromgid(new)
		raise ValueError, "Invalid group: %r" % new
	@group.fetch
	def group(self):
		return Group.fromgid(os.stat(self.path).st_gid)

	@param()
	def mode(self, new):
		if isinstance(new, int):
			return mode(new)
		raise ValueError, "Invalid mode: %r" % new
	@mode.fetch
	def mode(self):
		if os.path.exists(self.path):
			return mode(os.stat(self.path).st_mode)
		else:
			return mode(0644)

	@param()
	def content(self, new):
		if isinstance(new, (basestring, fact)) or new is None:
			return new
		raise ValueError, "Invalid file content: %r" % new
	@content.fetch
	def content(self):
		if os.path.exists(self.path):
			return open(self.path, 'rb').read()
		else:
			return None

	def create_folder(self):
		logger.debug('os.mkdir(%r)', self.path)
		os.mkdir(self.path)

	def create_file(self):
		logger.debug("open(%r, 'wb').write(~%s~)", self.path, md5sum(self.content()))
		open(self.path, 'wb').write(self.content())

	def create_link(self):
		logger.debug("os.symlink(%r, %r)", self.path, self.content())
		os.symlink(self.content(), self.path)

	def remove(self):
		if os.path.isdir(self.path):
			logger.debug('shutil.rmtree(%r)', self.path)
			self.manifest.safe or shutil.rmtree(self.path)
		else:
			logger.debug('os.unlink(%r)', self.path)
			os.unlink(self.path)

	def chown(self):
		s = os.stat(self.path)
		uid, gid = -1, -1
		if s.st_uid != self.owner().uid():
			uid = self.owner().uid()
		if s.st_gid != self.group().gid():
			gid = self.group().gid()
		if (uid, gid) != (-1, -1):
			logger.debug("os.lchown(%r, %r, %r)", self.path, uid, gid)
			os.lchown(self.path, uid, gid)

	def chmod(self):
		m = self.mode()
		if self.state() == 'folder':
			m = m.x_folder()
		logger.debug("os.lchmod(%r, %o)", self.path, m)

	def runners(self):
		state = self.state()
		exists = os.path.exists(self.path)
		if state == 'absent':
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
		self < Group(name)

	present = bool_param('present', True)

	@param()
	def password(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid password: %r" % new
	@password.fetch
	def password(self):
		return getpwd(self.name).pw_passwd

	@param(lambda self:getpwd(self.name).pw_uid)
	def uid(self, new):
		if not isinstance(new, (fact, int)):
			raise ValueError, "Invalid uid: %r" % new
		return new

	@param(lambda self:Group.fromgid(getpwd(self.name).pw_gid))
	def group(self, new):
		if isinstance(new, (Group, fact)):
			return new
		elif isinstance(new, basestring):
			return Group(new)
		elif isinstance(new, int):
			return Group.fromgid(new)
		raise ValueError, "Invalid Group: %r" % new

	@param(lambda self:getpwd(self.name).pw_gecos)
	def comment(self, new):
		if not isinstance(new, basestring):
			raise ValueError, "Invalid comment: %r" % new
		return new

	@param()
	def homedir(self, new):
		if isinstance(new, Path):
			return new
		elif isinstance(new, basestring):
			return Folder(new)
		raise ValueError, "Invalid homedir: %r" % new
	@homedir.fetch
	def homedir(self):
		try:
			return Folder(pwd.getpwnam(self.name).pw_dir)
		except KeyError:
			return Folder('/home/%s' % self.name, owner=self)

	@param(lambda self:getpwd(self.name).pw_shell or '/bin/sh')
	def shell(self, new):
		if isinstance(new, basestring):
			return new
		raise ValueError, "Invalid shell: %r" % new

	@param()
	def groups(self, new):
		if isinstance(new, (list,tuple,set)):
			return set(new)
		raise ValueError, "Invalid groups: %r" % new
	@groups.fetch
	def groups(self):
		try:
			return set(Group(g.gr_name) for g in grp.getgrall() if self.name in g.gr_mem)
		except KeyError:
			return set()

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

	present = bool_param('present', True)
	
	@param(lambda self:getgr(self.name).gr_gid)
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
		logger.debug(' '.join(map(str,cmd)))
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

class System(Definition):
	@ro_param
	def platform(self):
		return 'linux'

	@ro_param
	def distribution(self):
		return 'ubuntu'

	@ro_param
	def domain(self):
		return socket.getfqdn()

	@ro_param
	def hostname(self):
		return socket.gethostname()

System = System()

class Host(object):
	def __init__(self, match=''):
		self.match = match
		
	def __nonzero__(self):
		return self.match == '' or re.match(self.match, System.hostname()) is not None

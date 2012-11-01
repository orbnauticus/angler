#!/usr/bin/env python

from ..common import *
#from ..system import Path

import apt
import multiprocessing
import os
import sys

import logging
logger = logging.getLogger('apt')

class UpdatePackageCache(Definition):
	args = ['cache']

	update = bool_param('update', False)

	def runners(self):
		if self.update():
			yield self.do_update

	def do_update(self):
		logging.debug('Updating package cache')
		apt_cache.update()

class SilentAcquireProgress(apt.progress.base.AcquireProgress):
	pass

class SilentInstallProgress(apt.progress.base.InstallProgress):
	pass

class InstallPackages(Definition):
	force = bool_param('force', False)

	changes_found = bool_param('changes_found', False)

	upgrade = bool_param('upgrade', False)

	def do_upgrade(self):
		logger.debug('Upgrading packages')
		apt_cache.upgrade()

	def do_install(self):
		logger.debug('Committing changes to %i packages', len(apt_cache.get_changes()))
		ap = SilentAcquireProgress()
		ip = SilentInstallProgress()
		def commit(ap, ip):
			r = os.open(os.devnull, os.O_RDWR)
			for i in range(3):
				os.close(i)
				if r != i:
					os.dup2(r, i)
			apt_cache.commit(ap, ip)
		proc = multiprocessing.Process(target=commit, args=(ap, ip))
		proc.start()
		proc.join()
		logger.debug('Finished committing changes')

	def runners(self):
		if self.force() or apt_cache.get_changes():
			if self.update():
				yield self.do_update
			if self.upgrade():
				yield self.do_upgrade
			yield self.do_install

apt_cache = apt.cache.Cache()

Cache = UpdatePackageCache()
Commit = InstallPackages()
Cache > Commit

class Package(Definition):
	def __init__(self, name):
		Commit > self
		self.status = 'installed'

	@param('installed')
	def status(self, new):
		new = new.lower()
		if new == 'installed':
			Cache.update = True
			try:
				apt_cache[self.name].mark_install()
			except KeyError:
				pass
			return new
		elif new == 'removed':
			try:
				apt_cache[self.name].mark_delete()
			except KeyError:
				pass
			return new
		raise ValueError, "Invalid Package status: %r" % new

	@param()
	def source(self, new):
		if new is None:
			return new
		elif isinstance(new, basestring):
			return Path(new, state='file')
		elif isinstance(new, Path):
			return new
		raise ValueError, "Invalid source: %r"

	def dpkg_install(self):
		RUN('dpkg', '-i', self.source().path)

	def runners(self):
		if self.source() is not None:
			try:
				p = apt_cache[self.name]
			except KeyError:
				yield self.dpkg_install
		else:
			yield lambda:None

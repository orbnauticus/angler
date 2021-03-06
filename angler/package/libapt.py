#!/usr/bin/env python

from ..common import *

import apt
import multiprocessing
import os
import sys

logger = getLogger('apt')

apt_cache = apt.cache.Cache()

class UpdatePackageCache(Definition):
	update = param.boolean('update', False)

	def runners(self, notifiers):
		if self.update() or any(x.marked_install for x in apt_cache.get_changes()):
			yield self.do_update

	def do_update(self):
		logger.debug('Updating package cache')
		apt_cache.update()

class SilentAcquireProgress(apt.progress.base.AcquireProgress):
	pass

class SilentInstallProgress(apt.progress.base.InstallProgress):
	pass

class CommitPackageChanges(Definition):
	force = param.boolean('force', False)
	changes_found = param.boolean('changes_found', False)
	upgrade = param.boolean('upgrade', False)

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
		apt_cache.open()

	def runners(self, notifiers):
		if self.force() or apt_cache.get_changes():
			if self.upgrade():
				yield self.do_upgrade
			yield self.do_install

class Package(Definition):
	def __init__(self, name):
		Definition.__init__(self, name)
		CommitPackageChanges().requires(self)
		self.requires(UpdatePackageCache())
		self.dep_standin = CommitPackageChanges()

	@param.enum('installed', 'removed', default='installed')
	def state(self, new):
		return new.lower()

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

	def mark_install(self):
		logger.debug('Marking package %r for installation', self.name)
		apt_cache[self.name].mark_install()

	def mark_delete(self):
		logger.debug('Marking package %r for removal', self.name)
		apt_cache[self.name].mark_delete()

	def runners(self, notifiers):
		try:
			source, state, package = self.source(), self.state(), apt_cache[self.name]
		except KeyError:
			source, state, package = self.source(), self.state(), None
		if source is None:
			if package is None:
				raise KeyError, "Unable to find package %r" % self.name
			elif state == 'installed' and not package.is_installed:
				yield self.mark_install
			elif state == 'removed' and package.is_installed:
				yield self.mark_delete
		else:
			if state == 'installed' and package is None:
				yield self.dpkg_install
			elif state == 'removed' and package is not None:
				yield self.mark_delete

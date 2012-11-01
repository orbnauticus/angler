#!/usr/bin/env python

from ..common import *
#from ..system import System

if System.platform() == 'linux':
	if System.distribution() in ('ubuntu', 'debian'):
		from .libapt import Package
	elif System.distribution() in ('redhat', 'suse'):
		from .rpm import Package
	else:
		logging.warning('Package management is not available on this platform: %s, %s', System.platform(), System.distribution())

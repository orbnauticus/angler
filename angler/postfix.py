#!/usr/bin/env python

from .common import *

class conf(Definition):
	args = ['name']

	@param()
	def value(self, new):
		return new

	comment = bool_param('comment', False)

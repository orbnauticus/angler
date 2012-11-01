#!/usr/bin/env python

import logging

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

class Color(object):
	Black, Red, Green, Yellow, Blue, Magenta, Cyan, White = range(8)
	def __init__(self, foreground=None, background=None, bold=False):
		self.foreground = foreground
		self.background = background
		self.bold = bold

	@property
	def foreground_code(self):
		return None if self.foreground is None else str(self.foreground + 30)

	@property
	def background_code(self):
		return None if self.background is None else str(self.background + 40)

	@property
	def bold_code(self):
		return '1' if self.bold else ''

	def wrap(self, text):
		params = ';'.join(filter(None, (self.foreground_code, self.background_code, self.bold_code)))
		return '\x1b[%sm%s\x1b[0m' % (params, text)

class ColorStreamHandler(logging.StreamHandler):
	@property
	def is_tty(self):
		try:
			return self.stream.isatty()
		except AttributeError:
			return False

	color_map = {
		DEBUG: Color(Color.Blue),
		INFO: Color(Color.Cyan),
		WARNING: Color(Color.Yellow),
		ERROR: Color(Color.Red),
		CRITICAL: Color(Color.White, Color.Red, True),
	}

	def emit(self, record):
		try:
			message = self.format(record)
			self.stream.write(message)
			self.stream.write(getattr(self, 'terminator', '\n'))
			self.flush()
		except (KeyboardInterrupt, SystemExit):
			raise
		except:
			self.handleError(record)

	def format(self, record):
		message = logging.StreamHandler.format(self, record)
		if self.is_tty:
			message = self.color_map.get(record.levelno, Color()).wrap(message)
		return message

class AnglerFormatter(logging.Formatter):
	def format(self, record):
		record.levelname = record.levelname.rjust(5)
		record.name = record.name.center(max(len(x) for x in logging.Logger.manager.loggerDict))
		return logging.Formatter.format(self, record)

formatter = AnglerFormatter('%(levelname)s %(name)s: %(message)s')
csh = ColorStreamHandler()
csh.setFormatter(formatter)
logging.root.addHandler(csh)
logging.root.setLevel(DEBUG)

#!/usr/bin/env python3

from angler.core import Manifest, default_manifest, Session, setup
from angler.command import Add, Order, Apply, Setup
from angler.util import uri, key_value

import argparse
import cmd
import os
import shlex
import sys


def single_arg(string):
    values = shlex.split(string)
    if len(values) > 1:
        raise ValueError("Unexpected arguments: {}".format(values[1:]))
    return values[0]


class AnglerShell(cmd.Cmd):
    def __init__(self, manifest, history='~/.angler_history'):
        super(AnglerShell, self).__init__()
        self.isatty = sys.stdin.isatty()
        self.environment = dict()
        self.manifest = manifest
        self.session = Session(manifest)
        self.environment['manifest'] = manifest.database
        self.environment['curdir'] = ''
        self.prompt = '{manifest}#{curdir}⟫'
        self.environment['prompt2'] = '>'
        self.multiline = ''
        self.history = os.path.expanduser(history)
        try:
            import readline
            readline.read_history_file(self.history)
        except FileNotFoundError:
            pass
        except ImportError:
            pass
        else:
            import atexit
            atexit.register(readline.write_history_file, self.history)

    @property
    def prompt(self):
        if not self.isatty:
            return ''
        elif self.multiline:
            return self.environment['prompt2'] + ' '
        else:
            return self.environment['prompt'].format(**self.environment) + ' '

    @prompt.setter
    def prompt(self, new):
        self.environment['prompt'] = new

    def emptyline(self):
        pass

    def parseline(self, line):
        if self.multiline:
            line = '{}\n{}'.format(self.multiline, line)
        self.multiline = ''
        try:
            words = shlex.split(line)
        except ValueError as error:
            if error.args == ('No closing quotation',):
                self.multiline = line
                return None, None, ''
            elif error.args == ('No escaped character',):
                self.multiline = line[:-1]
                return None, None, ''
            else:
                raise
        if not words:
            return None, None, ''
        cmd, arg = words[0], words[1:]
        return cmd, arg, line

    def default(self, line):
        if line == 'EOF':
            if self.isatty:
                print('exit')
            return self.do_exit('')
        else:
            return super(AnglerShell, self).default(line)

    def do_exit(self, args):
        try:
            import readline
            last_index = readline.get_current_history_length()
            last_command = readline.get_history_item(last_index)
            if (last_command is not None and (last_command == 'exit'
                    or last_command.startswith('exit '))):
                readline.remove_history_item(last_index-1)
        except ImportError:
            pass
        return True

    def do_help(self, args):
        super(AnglerShell, self).do_help(args[0])

    do_setup = Setup.do()
    help_setup = Setup.help()

    do_add = Add.do()
    help_add = Add.help()

    do_order = Order.do()
    help_order = Order.help()

    do_apply = Apply.do()
    help_apply = Apply.help()

    def do_stub(self, args):
        print(args)

    def do_var(self, args):
        if not args:
            for key in sorted(self.environment):
                print('{}={!r}'.format(key, self.environment[key]))
            return
        key, successful, value = arg.partition('=')
        if successful:
            self.environment[key.strip()] = single_arg(value)
        else:
            key = arg.strip()
            print('{}={!r}'.format(key, self.environment[key]))

    def do_cd(self, args):
        self.environment['curdir'] = args[0]

    def do_ls(self, args):
        arg = (args[:0] or [self.environment['curdir']])[0]
        if not arg:
            for scheme in self.manifest.plugins:
                print('{}://'.format(scheme))
        else:
            print('Not Implemented!')

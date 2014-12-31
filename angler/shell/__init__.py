#!/usr/bin/env python3

from angler.core import Manifest, default_manifest, Session, setup
from angler.command import Add, Order, Apply, Setup
from angler.util import uri, key_value

from .shell import Lookup
from .vfs import VfsShell, SettingsVFS

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


class AnglerShell(VfsShell):
    def __init__(self, manifest, history='~/.angler_history', **kwargs):
        VfsShell.__init__(
            self,
            history,
            prompt='{manifest}:{pwd}⟫',
            startpath='/',
            pwdname='pwd',
            **kwargs)
        self.manifest = manifest
        self.environment['manifest'] = Lookup(self.manifest, attr='database')
        self.vfs.mkdir('/settings')
        self.vfs.mount('/settings', SettingsVFS(self.manifest))

    def do_help(self, args):
        super(AnglerShell, self).do_help(args[0] if args else '')

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

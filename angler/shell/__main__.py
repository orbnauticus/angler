#!/usr/bin/env python3

from ..core import Manifest, default_manifest, setup
from . import AnglerShell

import argparse
import os
import sys


parser = argparse.ArgumentParser()

parser.add_argument('stdin', nargs='?', type=argparse.FileType('r'),
                    metavar='command_file', default=sys.stdin)

parser.add_argument('-m', '--manifest', default=default_manifest)
parser.add_argument('-n', '--dryrun', action='store_true')
parser.add_argument('-c', '--command', action='append', default=(),
                    dest='commands')
parser.add_argument('-i', '--interactive', action='store_true')

args = parser.parse_args()

if not os.path.exists(args.manifest):
    setup(args.manifest)

manifest = Manifest(args.manifest)

try:
    shell = AnglerShell(manifest, stdin=args.stdin)
    shell.environment['dryrun'] = args.dryrun

    for command in args.commands:
        shell.onecmd(command)
    if not args.commands or args.interactive:
        shell.use_rawinput = shell.isatty
        shell.cmdloop()
except KeyboardInterrupt:
    print()
    exit(0)


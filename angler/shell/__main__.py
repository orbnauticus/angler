#!/usr/bin/env python3

from ..core import Manifest, default_manifest, setup
from . import AnglerShell

import argparse
import os


parser = argparse.ArgumentParser()

parser.add_argument('manifest', nargs='?', default=default_manifest)
parser.add_argument('-n', '--dryrun', action='store_true')

args = parser.parse_args()

if not os.path.exists(args.manifest):
    setup(args.manifest)

manifest = Manifest(args.manifest)

try:
    shell = AnglerShell(manifest)
    shell.environment['dryrun'] = args.dryrun
    shell.cmdloop()
except KeyboardInterrupt:
    print()
    exit(0)


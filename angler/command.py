
from angler.core import Manifest, default_manifest
from angler.util import uri, key_value

import argparse
from inspect import cleandoc

class Add(object):
    def __init__(self, manifest, uri, status, before, after):
        self.manifest = manifest
        self.uri = uri
        self.status = status
        self.before = before
        self.after = after

    @classmethod
    def help(self):
        return cleandoc("""
        add uri [status] [property=value [property=value ...]]

        Add a node at uri to the manifest.
        """)

    @classmethod
    def from_arguments(cls, manifest=None, argv=None, exit=True):
        parser = argparse.ArgumentParser()

        parser.add_argument('uri', type=uri)
        parser.add_argument('status', nargs='?')
        parser.add_argument('properties', metavar='property=value',
                            type=key_value, nargs='*')

        if manifest is None:
            parser.add_argument('-m', '--manifest', default=default_manifest)

        parser.add_argument('-b', '--before', action='append', default=[])
        parser.add_argument('-a', '--after', action='append', default=[])

        args = parser.parse_args(argv)

        if manifest is None:
            manifest = Manifest(args.manifest)

        if args.status is None:
            args.status = {'': {}}
        elif '=' in args.status:
            first = key_value(args.status)
            args.status = {'': {first[0]: first[1]}}
        else:
            args.status = {args.status: {}}

        key = list(args.status.keys())[0]

        if args.properties:
            args.status[key].update(dict(args.properties))

        return cls(manifest, args.uri, args.status, args.before, args.after)

    def run(self):
        self.manifest.insert_node(self.uri, self.status)

        for node in self.before:
            self.manifest.insert_edge(self.uri, node)

        for node in self.after:
            self.manifest.insert_edge(node, self.uri)

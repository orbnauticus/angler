
from angler.core import Manifest, default_manifest, setup
from angler.util import uri, key_value

import argparse
from inspect import cleandoc


class Command(object):
    @classmethod
    def parser(cls):
        return argparse.ArgumentParser()

    @classmethod
    def parse_args(cls, manifest=None, argv=None, exit=True):
        parser = cls.parser()

        if manifest is None:
            parser.add_argument('--manifest', '-m', default=default_manifest)

        try:
            args = parser.parse_args(argv)
        except SystemExit:
            if exit:
                raise
            else:
                return

        args.manifest = (Manifest(args.manifest) if manifest is None
                         else manifest)
        return args

    @classmethod
    def from_arguments(cls, manifest=None, argv=None, exit=True):
        args = cls.parse_args(manifest, argv, exit)
        if args is not None:
            return cls(**vars(args))

    @classmethod
    def do(cls):
        def do_command(self, args):
            obj = cls.from_arguments(self.manifest, args, exit=False)
            if obj is not None:
                obj.run()
        return do_command

    @classmethod
    def help(cls):
        def help_command(self):
            print (cleandoc(cls.__doc__) if cls.__doc__ else
                    "No help available.")
        return help_command


class Setup(Command):
    def __init__(self, manifest):
        self.manifest = manifest

    @classmethod
    def parse_args(cls, manifest=None, argv=None, exit=True):
        parser = cls.parser()

        parser.add_argument('--manifest', '-m', default=default_manifest)

        try:
            args = parser.parse_args(argv)
        except SystemExit:
            if exit:
                raise
            else:
                return

        return args

    def run(self):
        setup(self.manifest)


class Add(Command):
    """
    add uri [status] [property=value [property=value ...]]

    Add a node at uri to the manifest.
    """
    def __init__(self, manifest, uri, status, before, after):
        self.manifest = manifest
        self.uri = uri
        self.status = status
        self.before = before
        self.after = after

    @classmethod
    def parser(cls):
        parser = super(Add, cls).parser()

        parser.add_argument('uri', type=uri)
        parser.add_argument('status', nargs='?')
        parser.add_argument('properties', metavar='property=value',
                            type=key_value, nargs='*')

        parser.add_argument('-b', '--before', action='append', default=[])
        parser.add_argument('-a', '--after', action='append', default=[])
        return parser

    @classmethod
    def parse_args(cls, manifest=None, argv=None, exit=True):
        args = super(Add, cls).parse_args(manifest, argv, exit)

        if args is None:
            return

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
        del args.properties

        return args

    def run(self):
        self.manifest.insert_node(self.uri, self.status)

        for node in self.before:
            self.manifest.insert_edge(self.uri, node)

        for node in self.after:
            self.manifest.insert_edge(node, self.uri)


from itertools import tee


class Order(Command):
    """
    usage: order uri uri [uri ...]

    Assert an order for a chain of two or more nodes
    """
    def __init__(self, manifest, nodes):
        self.manifest = manifest
        self.nodes = nodes

    @classmethod
    def parser(cls):
        parser = super(Order, cls).parser()
        parser.add_argument('nodes', nargs='+', type=uri, metavar='uri')
        return parser

    def run(self):
        sources, sinks = tee(self.nodes)
        next(sinks, None)

        for source, sink in zip(sources, sinks):
            self.manifest.insert_edge(source, sink)


class Apply(Command):
    def __init__(self, manifest, swap, dryrun):
        self.manifest = manifest
        self.swap = swap
        self.dryrun = dryrun

    @classmethod
    def parser(cls):
        parser = super(Apply, cls).parser()
        parser.add_argument('--swap', '-s', action='store_true',
                            help='Reverse order of nodes in each stage.'
                                 ' Useful for checking if there are any missing'
                                 ' relationships')
        parser.add_argument('--dryrun', '-n', action='store_true',
                            help='List what actions would be taken without making'
                                 ' any changes')
        return parser

    def run(self):
        self.manifest.run_once(self.swap, dryrun=self.dryrun)

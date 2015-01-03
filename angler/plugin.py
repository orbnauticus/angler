
from .util import urisplit, urijoin

from abc import abstractmethod, ABCMeta

import logging


class Definition(metaclass=ABCMeta):
    def __init__(self, scheme, host, path, query, fragment, value):
        self.scheme = scheme
        self.host = host
        self.path = path
        self.query = query
        self.fragment = fragment
        self.value = value
        self.logger = logging.getLogger(scheme)

    def __hash__(self):
        return hash((self.scheme, self.host, self.path, self.query,
                     self.fragment))

    @classmethod
    def from_node(cls, node):
        return cls(value=node.value, *urisplit(node.uri))

    def get_uri(self):
        return urijoin(self.scheme, self.host, self.path, self.query,
                       self.fragment)

    def found_node(self, session):
        pass

    def found_incoming_edge(self, session, source):
        pass

    def found_outgoing_edge(self, session, sink):
        pass

    @abstractmethod
    def get_state(self):
        return

    @abstractmethod
    def set_state(self, current_state):
        return

    def copy(self, **replacements):
        kwargs = dict(scheme=self.scheme, host=self.host, path=self.path,
                      query=self.query, fragment=self.fragment,
                      value=self.value)
        kwargs.update(replacements)
        return self.__class__(**kwargs)


def main(*plugins):
    import itertools
    import json
    import sys

    handlers = dict(
        (scheme, plugin) for plugin in plugins for scheme in
        getattr(plugin, 'schemes', [plugin.__name__.lower()]))

    args = dict(itertools.zip_longest(
        ['command', 'scheme', 'path', 'query', 'fragment'], sys.argv[1:]))

    if args['command'] == 'list':
        print('\n'.join(handlers))
    elif args['command'] == 'get':
        plugin = handlers[args['scheme']]
        definition = plugin(args['scheme'], '', args['path'], args['query'],
                            args['fragment'], None)
        json.dump(definition.get_state(), sys.stdout)
    elif args['command'] == 'set':
        plugin = handlers[args['scheme']]
        definition = plugin(args['scheme'], '', args['path'], args['query'],
                            args['fragment'], json.load(sys.stdin))
        definition.set_state()
    else:
        print("Usage: {} command scheme path query".format(sys.argv[0]))

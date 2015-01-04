
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

    @property
    def state(self):
        return list(self.value.keys())[0]

    @property
    def properties(self):
        return self.value[self.state]

    def __hash__(self):
        return hash((self.scheme, self.host, self.path, self.query,
                     self.fragment))

    @classmethod
    def from_node(cls, node):
        return cls(value=node.value, *urisplit(node.uri))

    def replace(self, **kwargs):
        params = dict(scheme=self.scheme, host=self.host, path=self.path,
                      query=self.query, fragment=self.fragment,
                      value=self.value)
        params.update(kwargs)
        return self.__class__(**params)

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

    #sys.argv[1:] = ['node', 'path', '', '/tmp/angler', '', '']
    #import io
    ##sys.stdin = io.StringIO('{"absent": {}}\n{"file": {}}\n')
    #sys.stdin = io.StringIO('')

    class fake_manifest(object):
        def __init__(self, node):
            self.node = node

        def add_definition(self, definition):
            print("node", definition.get_uri(), json.dumps(definition.value))

        def add_order(self, before, after):
            print("edge", before.get_uri(), after.get_uri())

    def fail():
        print("""Usage: {} list|get|set|node|incoming|outgoing ...

list
        List all schemes this plugin can handle, one per line

get scheme host path query fragment
        Get the current status of this node, output as a json object with
        one key.

set scheme host path query fragment
        Set the status of this node. The old and new values are passed as
        json objects to stdin, one per line.

node scheme host path query fragment
        Optional hook when a node is encountered for the first time. Prints
        lines for new automatic nodes and edges in the form:
        "node uri value_json" or "edge source sink"

incoming|outgoing scheme host path query fragment scheme2 host2 ...
        Optional hook when an incoming or outgoing edge is encountered for the
        first time. Prints lines for new automatic nodes and edges in the form:
        "node uri value_json" or "edge source sink"
""".format(sys.argv[0]))
        exit(1)

    handlers = dict(
        (scheme, plugin) for plugin in plugins for scheme in
        getattr(plugin, 'schemes', [plugin.__name__.lower()]))

    def get_uri():
        return dict(
            scheme=sys.argv.pop(1),
            host=sys.argv.pop(1),
            path=sys.argv.pop(1),
            query=sys.argv.pop(1),
            fragment=sys.argv.pop(1),
        )

    command = sys.argv.pop(1) if len(sys.argv) > 1 else None

    if command == 'list':
        print('\n'.join(handlers))
        exit(0)
    elif len(sys.argv[1:]) < 5:
        fail()
    else:
        uri = get_uri()
        plugin = handlers[uri['scheme']]

    if command == 'set':
        old = json.loads(sys.stdin.readline())
        new = json.loads(sys.stdin.readline())
        definition = plugin(value=new, **uri)
    else:
        definition = plugin(value=None, **uri)

    if command == 'get':
        json.dump(definition.get_state(), sys.stdout)
        sys.stdout.write('\n')
        sys.stdout.flush()
    elif command == 'set':
        definition.set_state(old, new)
    elif command == 'node':
        manifest = fake_manifest(definition)
        definition.found_node(manifest)
    elif command in ('incoming', 'outgoing'):
        manifest = fake_manifest(definition)
        other = get_uri()
        if command == 'incoming':
            definition.found_incoming_edge(manifest, other)
        elif command == 'outgoing':
            definition.found_outgoing_edge(manifest, other)
    else:
        fail()


from abc import abstractmethod, ABCMeta

import logging
import re

def urisplit(uri):
    pattern = "^([a-zA-Z+_-]+)://([^/]*)(/[^?#]*)(?:\?([^#]*))?(?:#(.*))?$"
    match = re.match(pattern, uri)
    if match is None:
        raise ValueError("Unable to parse uri {!r}".format(uri))
    return match.groups()


def urijoin(scheme, host, path, query, fragment):
    if not path.startswith('/'):
        raise ValueError("Invalid 'path': {!r}".format(path))
    return '{scheme}://{host}{path}{query}{fragment}'.format(
        scheme=scheme,
        host=host,
        path=path,
        query=(query or '') and '?' + query,
        fragment=(fragment or '') and '?' + fragment
    )


class Plugin(metaclass=ABCMeta):
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
